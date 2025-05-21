import torch
import numpy as np
from typing import Dict, Any
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    confusion_matrix,
    roc_auc_score,
    mean_squared_error,
    r2_score
)

def compute_classification_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_prob: np.ndarray = None) -> Dict[str, float]:
    """Compute classification metrics."""
    metrics = {}
    
    # Basic metrics
    metrics['accuracy'] = float(accuracy_score(y_true, y_pred))
    
    # Precision, recall, F1 (macro average)
    precision, recall, f1, _ = precision_recall_fscore_support(y_true, y_pred, average='macro')
    metrics['precision'] = float(precision)
    metrics['recall'] = float(recall)
    metrics['f1_score'] = float(f1)
    
    # Confusion matrix
    cm = confusion_matrix(y_true, y_pred)
    metrics['confusion_matrix'] = cm.tolist()
    
    # ROC AUC (if probabilities are provided)
    if y_prob is not None:
        if y_prob.shape[1] == 2:  # Binary classification
            metrics['roc_auc'] = float(roc_auc_score(y_true, y_prob[:, 1]))
        else:  # Multi-class
            metrics['roc_auc'] = float(roc_auc_score(y_true, y_prob, multi_class='ovr'))
    
    return metrics

def compute_regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Compute regression metrics."""
    metrics = {}
    
    # Mean squared error
    metrics['mse'] = float(mean_squared_error(y_true, y_pred))
    metrics['rmse'] = float(np.sqrt(metrics['mse']))
    
    # R-squared score
    metrics['r2_score'] = float(r2_score(y_true, y_pred))
    
    # Mean absolute error
    metrics['mae'] = float(np.mean(np.abs(y_true - y_pred)))
    
    # Mean absolute percentage error
    metrics['mape'] = float(np.mean(np.abs((y_true - y_pred) / y_true)) * 100)
    
    return metrics

def compute_metrics(model: torch.nn.Module, data_loader: torch.utils.data.DataLoader, 
                   device: torch.device) -> Dict[str, Any]:
    """Compute all relevant metrics for the model."""
    model.eval()
    all_preds = []
    all_probs = []
    all_targets = []
    
    with torch.no_grad():
        for data, target in data_loader:
            data = data.to(device)
            target = target.to(device)
            
            # Forward pass
            output = model(data)
            
            # Store predictions and targets
            if isinstance(output, tuple):
                output = output[0]  # Some models return multiple outputs
            
            # Handle different output types
            if output.shape[1] > 1:  # Classification
                probs = torch.softmax(output, dim=1)
                preds = torch.argmax(output, dim=1)
                all_probs.append(probs.cpu().numpy())
            else:  # Regression
                preds = output.squeeze()
                all_probs = None
            
            all_preds.append(preds.cpu().numpy())
            all_targets.append(target.cpu().numpy())
    
    # Concatenate all batches
    y_pred = np.concatenate(all_preds)
    y_true = np.concatenate(all_targets)
    y_prob = np.concatenate(all_probs) if all_probs else None
    
    # Compute metrics based on problem type
    if y_prob is not None:  # Classification
        metrics = compute_classification_metrics(y_true, y_pred, y_prob)
    else:  # Regression
        metrics = compute_regression_metrics(y_true, y_pred)
    
    return metrics

class MetricTracker:
    """Class to track metrics during training."""
    def __init__(self):
        self.metrics = {}
        self.current_epoch = 0
    
    def update(self, metric_name: str, value: float, epoch: int = None):
        """Update a metric value."""
        if epoch is not None:
            self.current_epoch = epoch
        
        if metric_name not in self.metrics:
            self.metrics[metric_name] = []
        
        # Extend list if needed
        while len(self.metrics[metric_name]) <= self.current_epoch:
            self.metrics[metric_name].append(None)
        
        self.metrics[metric_name][self.current_epoch] = value
    
    def get_latest(self, metric_name: str) -> float:
        """Get the latest value for a metric."""
        if metric_name not in self.metrics:
            raise KeyError(f"Metric {metric_name} not found")
        return self.metrics[metric_name][self.current_epoch]
    
    def get_best(self, metric_name: str, mode: str = 'min') -> float:
        """Get the best value for a metric."""
        if metric_name not in self.metrics:
            raise KeyError(f"Metric {metric_name} not found")
        
        values = [v for v in self.metrics[metric_name] if v is not None]
        if not values:
            return None
        
        return min(values) if mode == 'min' else max(values)
    
    def get_history(self, metric_name: str) -> list:
        """Get the full history of a metric."""
        if metric_name not in self.metrics:
            raise KeyError(f"Metric {metric_name} not found")
        return self.metrics[metric_name]
    
    def has_improved(self, metric_name: str, mode: str = 'min') -> bool:
        """Check if the metric has improved in the current epoch."""
        if metric_name not in self.metrics:
            raise KeyError(f"Metric {metric_name} not found")
        
        current = self.get_latest(metric_name)
        best = self.get_best(metric_name, mode)
        
        if current is None or best is None:
            return False
        
        return current < best if mode == 'min' else current > best 