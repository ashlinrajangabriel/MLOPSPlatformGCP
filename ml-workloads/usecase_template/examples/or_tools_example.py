import os
import yaml
import numpy as np
import torch.distributed as dist
from typing import Dict, Any
import mlflow
from google.cloud import storage
import uuid

from ..training.utils.or_models import RoutingOptimizer, SchedulingOptimizer

def load_data(config: Dict[str, Any], problem_type: str) -> Dict[str, Any]:
    """Load problem data from GCS."""
    if problem_type == 'routing':
        # Load routing problem data
        distances = np.load(config['routing']['distance_matrix_path'])
        demands = np.load(config['routing']['demands_path'])
        time_windows = np.load(config['routing']['time_windows_path'])
        
        return {
            'distances': distances,
            'demands': demands,
            'time_windows': time_windows,
            'num_vehicles': config['routing']['num_vehicles'],
            'capacity': config['routing']['capacity'],
            'depot': config['routing']['depot']
        }
    
    elif problem_type == 'scheduling':
        # Load scheduling problem data
        processing_times = np.load(config['scheduling']['processing_times_path'])
        due_dates = np.load(config['scheduling']['due_dates_path'])
        release_dates = np.load(config['scheduling']['release_dates_path'])
        priorities = np.load(config['scheduling']['priorities_path'])
        
        return {
            'processing_times': processing_times,
            'due_dates': due_dates,
            'release_dates': release_dates,
            'priorities': priorities,
            'num_machines': config['scheduling']['num_machines']
        }
    
    else:
        raise ValueError(f"Unknown problem type: {problem_type}")

def setup_distributed(config: Dict[str, Any]):
    """Initialize distributed environment."""
    if config['distributed']['enabled']:
        dist.init_process_group(
            backend=config['distributed']['backend'],
            init_method=config['distributed']['init_method'],
            world_size=config['distributed']['world_size'],
            rank=config['distributed']['rank']
        )

def solve_optimization_problem(config_path: str, problem_type: str):
    """Solve optimization problem using parallel OR-Tools with spot instance support."""
    # Load configuration
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Setup distributed environment
    setup_distributed(config)
    
    # Initialize MLflow
    mlflow.set_tracking_uri(config['mlflow']['tracking_uri'])
    mlflow.set_experiment(config['mlflow']['experiment_name'])
    
    # Generate unique run ID for checkpointing
    run_id = str(uuid.uuid4())
    
    with mlflow.start_run(run_name=config['mlflow']['run_name']) as run:
        # Log parameters
        mlflow.log_params({
            'solver_type': config['solver']['type'],
            'time_limit': config['solver']['time_limit'],
            'num_workers': config['solver']['num_workers'],
            'problem_type': problem_type,
            'spot_enabled': config['spot']['enabled'],
            'run_id': run_id
        })
        
        try:
            # Load problem data
            data = load_data(config, problem_type)
            
            # Create appropriate optimizer with spot instance support
            if problem_type == 'routing':
                optimizer = RoutingOptimizer(config['solver'], run_id=run_id)
            elif problem_type == 'scheduling':
                optimizer = SchedulingOptimizer(config['solver'], run_id=run_id)
            else:
                raise ValueError(f"Unknown problem type: {problem_type}")
            
            # Solve problem in parallel with spot instance handling
            solution = optimizer.parallel_solve(data)
            
            # Log results (only on rank 0 if distributed)
            if not config['distributed']['enabled'] or dist.get_rank() == 0:
                if solution and solution['status'] in ['OPTIMAL', 'FEASIBLE']:
                    mlflow.log_metrics({
                        'objective_value': solution['objective'],
                        'solve_time': optimizer.time_limit  # Actual solve time if available
                    })
                    
                    # Log solution visualization if available
                    if hasattr(optimizer, 'visualize_solution'):
                        fig = optimizer.visualize_solution(solution['solution'], data)
                        mlflow.log_figure(fig, 'solution_visualization.png')
                    
                    # Log checkpoint information
                    if config['spot']['checkpointing']['enabled']:
                        mlflow.log_param('checkpoint_path', 
                                       f"gs://{config['spot']['checkpointing']['gcs_bucket']}/"
                                       f"{config['spot']['checkpointing']['gcs_path'].format(run_id=run_id)}")
                
                else:
                    print(f"No solution found. Status: {solution['status'] if solution else 'None'}")
        
        except Exception as e:
            print(f"Error during optimization: {e}")
            # Log error but don't fail - checkpoint should be saved by the optimizer
            if not config['distributed']['enabled'] or dist.get_rank() == 0:
                mlflow.log_param('error', str(e))
        
        finally:
            # Cleanup
            if config['distributed']['enabled']:
                dist.destroy_process_group()

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Solve optimization problem using parallel OR-Tools')
    parser.add_argument('--config', type=str, required=True, help='Path to configuration file')
    parser.add_argument('--problem-type', type=str, choices=['routing', 'scheduling'],
                      required=True, help='Type of optimization problem to solve')
    
    args = parser.parse_args()
    solve_optimization_problem(args.config, args.problem_type) 