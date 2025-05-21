import torch
import torch.nn as nn
import torchvision.models as models
from typing import Dict, Any

class CustomModel(nn.Module):
    """Custom PyTorch model example."""
    def __init__(self, input_dim: int, hidden_dim: int, output_dim: int):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(hidden_dim, output_dim)
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)

class CNNModel(nn.Module):
    """Custom CNN model example."""
    def __init__(self, num_channels: int, num_classes: int):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(num_channels, 64, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2)
        )
        
        self.classifier = nn.Sequential(
            nn.AdaptiveAvgPool2d((1, 1)),
            nn.Flatten(),
            nn.Linear(256, 512),
            nn.ReLU(),
            nn.Dropout(0.5),
            nn.Linear(512, num_classes)
        )
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = self.classifier(x)
        return x

def get_pretrained_model(model_name: str, num_classes: int, pretrained: bool = True) -> nn.Module:
    """Get a pretrained model from torchvision."""
    if not hasattr(models, model_name):
        raise ValueError(f"Model {model_name} not found in torchvision.models")
    
    # Get the model constructor
    model_fn = getattr(models, model_name)
    
    # Load pretrained model
    if pretrained:
        model = model_fn(weights='IMAGENET1K_V1')
    else:
        model = model_fn(weights=None)
    
    # Modify the last layer for our number of classes
    if hasattr(model, 'fc'):
        in_features = model.fc.in_features
        model.fc = nn.Linear(in_features, num_classes)
    elif hasattr(model, 'classifier'):
        if isinstance(model.classifier, nn.Sequential):
            in_features = model.classifier[-1].in_features
            model.classifier[-1] = nn.Linear(in_features, num_classes)
        else:
            in_features = model.classifier.in_features
            model.classifier = nn.Linear(in_features, num_classes)
    
    return model

def get_model(config: Dict[str, Any]) -> nn.Module:
    """Model factory function."""
    model_type = config['type'].lower()
    
    if model_type == 'custom':
        return CustomModel(
            input_dim=config.get('input_dim', 784),
            hidden_dim=config.get('hidden_dim', 256),
            output_dim=config['num_classes']
        )
    
    elif model_type == 'cnn':
        return CNNModel(
            num_channels=config.get('num_channels', 3),
            num_classes=config['num_classes']
        )
    
    elif model_type in dir(models):
        return get_pretrained_model(
            model_name=model_type,
            num_classes=config['num_classes'],
            pretrained=config.get('pretrained', True)
        )
    
    else:
        raise ValueError(f"Unknown model type: {model_type}")

def get_optimizer(model: nn.Module, config: Dict[str, Any]) -> torch.optim.Optimizer:
    """Get optimizer for the model."""
    optimizer_name = config['optimizer'].lower()
    lr = config.get('learning_rate', 0.001)
    
    if optimizer_name == 'adam':
        return torch.optim.Adam(
            model.parameters(),
            lr=lr,
            weight_decay=config.get('weight_decay', 0)
        )
    elif optimizer_name == 'sgd':
        return torch.optim.SGD(
            model.parameters(),
            lr=lr,
            momentum=config.get('momentum', 0.9),
            weight_decay=config.get('weight_decay', 0)
        )
    else:
        raise ValueError(f"Unknown optimizer: {optimizer_name}")

def get_scheduler(optimizer: torch.optim.Optimizer, config: Dict[str, Any]) -> torch.optim.lr_scheduler._LRScheduler:
    """Get learning rate scheduler."""
    scheduler_name = config.get('scheduler', '').lower()
    
    if not scheduler_name:
        return None
    
    if scheduler_name == 'steplr':
        return torch.optim.lr_scheduler.StepLR(
            optimizer,
            step_size=config.get('scheduler_step_size', 30),
            gamma=config.get('scheduler_gamma', 0.1)
        )
    elif scheduler_name == 'cosine':
        return torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer,
            T_max=config.get('num_epochs', 100),
            eta_min=config.get('scheduler_min_lr', 0)
        )
    else:
        raise ValueError(f"Unknown scheduler: {scheduler_name}")

def get_loss_function(config: Dict[str, Any]) -> nn.Module:
    """Get loss function."""
    loss_name = config.get('loss_function', 'cross_entropy').lower()
    
    if loss_name == 'cross_entropy':
        return nn.CrossEntropyLoss()
    elif loss_name == 'mse':
        return nn.MSELoss()
    elif loss_name == 'bce':
        return nn.BCEWithLogitsLoss()
    else:
        raise ValueError(f"Unknown loss function: {loss_name}") 