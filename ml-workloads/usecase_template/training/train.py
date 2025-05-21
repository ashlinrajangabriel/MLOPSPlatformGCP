import os
import argparse
import yaml
import torch
import torch.distributed as dist
import torch.nn as nn
import torch.optim as optim
from torch.nn.parallel import DistributedDataParallel
from torch.utils.data.distributed import DistributedSampler
from torch.utils.data import DataLoader
import mlflow
from google.cloud import storage

from .utils.data import get_dataset
from .utils.models import get_model
from .utils.metrics import compute_metrics

def setup_distributed(rank, world_size):
    """Initialize distributed training."""
    os.environ['MASTER_ADDR'] = 'localhost'
    os.environ['MASTER_PORT'] = '12355'
    dist.init_process_group("nccl", rank=rank, world_size=world_size)

def cleanup_distributed():
    """Cleanup distributed training."""
    dist.destroy_process_group()

def save_checkpoint(model, optimizer, epoch, run_id, config):
    """Save model checkpoint to GCS."""
    checkpoint = {
        'epoch': epoch,
        'model_state_dict': model.module.state_dict() if hasattr(model, 'module') else model.state_dict(),
        'optimizer_state_dict': optimizer.state_dict()
    }
    
    local_path = f'/tmp/checkpoint_{epoch}.pt'
    torch.save(checkpoint, local_path)
    
    # Upload to GCS
    storage_client = storage.Client()
    bucket = storage_client.bucket(config['training']['checkpointing']['gcs_bucket'])
    gcs_path = config['training']['checkpointing']['gcs_path'].format(run_id=run_id)
    blob = bucket.blob(f"{gcs_path}/checkpoint_{epoch}.pt")
    blob.upload_from_filename(local_path)
    os.remove(local_path)

def load_checkpoint(model, optimizer, run_id, config):
    """Load latest checkpoint from GCS."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(config['training']['checkpointing']['gcs_bucket'])
    gcs_path = config['training']['checkpointing']['gcs_path'].format(run_id=run_id)
    
    # List all checkpoints and get the latest
    blobs = bucket.list_blobs(prefix=gcs_path)
    latest_checkpoint = max(blobs, key=lambda x: int(x.name.split('_')[-1].split('.')[0]))
    
    local_path = '/tmp/checkpoint.pt'
    latest_checkpoint.download_to_filename(local_path)
    
    checkpoint = torch.load(local_path)
    if hasattr(model, 'module'):
        model.module.load_state_dict(checkpoint['model_state_dict'])
    else:
        model.load_state_dict(checkpoint['model_state_dict'])
    optimizer.load_state_dict(checkpoint['optimizer_state_dict'])
    os.remove(local_path)
    return checkpoint['epoch']

def train(rank, world_size, config_path):
    """Main training function."""
    # Load configuration
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Setup distributed training
    if config['training']['distributed']:
        setup_distributed(rank, world_size)
    
    # Set device
    device = torch.device(f"cuda:{rank}" if torch.cuda.is_available() else "cpu")
    
    # Initialize MLflow
    mlflow.set_tracking_uri(config['mlflow']['tracking_uri'])
    mlflow.set_experiment(config['mlflow']['experiment_name'])
    
    with mlflow.start_run(run_name=config['mlflow']['run_name']) as run:
        run_id = run.info.run_id
        
        # Log parameters
        mlflow.log_params({
            "model_type": config['model']['type'],
            "learning_rate": config['training']['learning_rate'],
            "batch_size": config['training']['batch_size'],
            "num_epochs": config['training']['num_epochs']
        })
        
        # Create model
        model = get_model(config['model'])
        model = model.to(device)
        
        if config['training']['distributed']:
            model = DistributedDataParallel(model, device_ids=[rank])
        
        # Setup optimizer and loss
        optimizer = getattr(optim, config['training']['optimizer'])(
            model.parameters(), 
            lr=config['training']['learning_rate']
        )
        criterion = getattr(nn, config['training']['loss_function'])()
        
        # Load checkpoint if exists
        start_epoch = 0
        if config['training']['checkpointing']['enabled']:
            try:
                start_epoch = load_checkpoint(model, optimizer, run_id, config)
            except Exception as e:
                print(f"No checkpoint found or error loading checkpoint: {e}")
        
        # Setup data loaders
        train_dataset = get_dataset(config['data']['train_path'])
        val_dataset = get_dataset(config['data']['val_path'])
        
        if config['training']['distributed']:
            train_sampler = DistributedSampler(train_dataset)
            val_sampler = DistributedSampler(val_dataset)
        else:
            train_sampler = None
            val_sampler = None
        
        train_loader = DataLoader(
            train_dataset, 
            batch_size=config['training']['batch_size'],
            sampler=train_sampler,
            num_workers=config['data']['num_workers'],
            pin_memory=config['data']['pin_memory']
        )
        
        val_loader = DataLoader(
            val_dataset,
            batch_size=config['training']['batch_size'],
            sampler=val_sampler,
            num_workers=config['data']['num_workers'],
            pin_memory=config['data']['pin_memory']
        )
        
        # Training loop
        best_val_loss = float('inf')
        patience_counter = 0
        
        for epoch in range(start_epoch, config['training']['num_epochs']):
            model.train()
            train_loss = 0.0
            
            if train_sampler:
                train_sampler.set_epoch(epoch)
            
            for batch_idx, (data, target) in enumerate(train_loader):
                data, target = data.to(device), target.to(device)
                
                optimizer.zero_grad()
                output = model(data)
                loss = criterion(output, target)
                loss.backward()
                optimizer.step()
                
                train_loss += loss.item()
                
                # Log metrics
                if batch_idx % config['mlflow']['metrics']['log_frequency'] == 0:
                    mlflow.log_metrics({
                        "train_loss": loss.item(),
                        "epoch": epoch,
                        "batch": batch_idx
                    }, step=epoch * len(train_loader) + batch_idx)
            
            # Validation
            model.eval()
            val_loss = 0.0
            with torch.no_grad():
                for data, target in val_loader:
                    data, target = data.to(device), target.to(device)
                    output = model(data)
                    val_loss += criterion(output, target).item()
            
            val_loss /= len(val_loader)
            train_loss /= len(train_loader)
            
            # Log epoch metrics
            metrics = {
                "train_loss_epoch": train_loss,
                "val_loss_epoch": val_loss,
                "epoch": epoch
            }
            
            # Compute custom metrics
            custom_metrics = compute_metrics(model, val_loader, device)
            metrics.update(custom_metrics)
            
            mlflow.log_metrics(metrics, step=epoch)
            
            # Save checkpoint
            if config['training']['checkpointing']['enabled'] and epoch % config['training']['checkpointing']['frequency'] == 0:
                save_checkpoint(model, optimizer, epoch, run_id, config)
            
            # Early stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
            else:
                patience_counter += 1
            
            if patience_counter >= config['training']['early_stopping']['patience']:
                print(f"Early stopping triggered at epoch {epoch}")
                break
        
        # Save final model
        if rank == 0:
            mlflow.pytorch.log_model(model, "model")
    
    if config['training']['distributed']:
        cleanup_distributed()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True, help="Path to config file")
    args = parser.parse_args()
    
    with open(args.config) as f:
        config = yaml.safe_load(f)
    
    if config['training']['distributed']:
        world_size = torch.cuda.device_count()
        torch.multiprocessing.spawn(
            train,
            args=(world_size, args.config),
            nprocs=world_size,
            join=True
        )
    else:
        train(0, 1, args.config) 