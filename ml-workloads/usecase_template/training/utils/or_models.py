import torch
import torch.nn as nn
import torch.distributed as dist
from ortools.sat.python import cp_model
from ortools.linear_solver import pywraplp
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import os
import signal
import time
from google.cloud import storage
import json
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError

class TimeoutManager:
    """Manager for handling various timeouts."""
    def __init__(self, config: Dict[str, Any]):
        self.timeouts = config['timeouts']
        self.start_time = time.time()
        self.last_improvement_time = self.start_time
        self.best_objective = float('inf')
    
    def check_total_runtime(self) -> bool:
        """Check if total runtime exceeded."""
        return (time.time() - self.start_time) >= self.timeouts['total_runtime']
    
    def check_improvement_timeout(self, current_objective: float) -> bool:
        """Check if time without improvement exceeded."""
        if current_objective < self.best_objective:
            self.best_objective = current_objective
            self.last_improvement_time = time.time()
            return False
        return (time.time() - self.last_improvement_time) >= self.timeouts['improvement']
    
    def run_with_timeout(self, func: callable, timeout_type: str, *args, **kwargs) -> Any:
        """Run function with specified timeout."""
        timeout = self.timeouts.get(timeout_type)
        if not timeout:
            return func(*args, **kwargs)
        
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func, *args, **kwargs)
            try:
                return future.result(timeout=timeout)
            except TimeoutError:
                raise TimeoutError(f"Operation timed out after {timeout} seconds")

class SpotInstanceHandler:
    """Handler for spot instance termination."""
    def __init__(self, config: Dict[str, Any]):
        self.termination_file = "/spot/termination-notice"
        self.termination_period = config['spot'].get('termination_period', 300)
        self.termination_time = None
        self._setup_termination_handler()
    
    def _setup_termination_handler(self):
        """Setup signal handler for spot instance termination."""
        def handler(signum, frame):
            self.termination_time = time.time()
        signal.signal(signal.SIGTERM, handler)
    
    def should_checkpoint(self) -> bool:
        """Check if we should checkpoint due to imminent termination."""
        if self.termination_time is None:
            return False
        return (time.time() - self.termination_time) >= self.termination_period
    
    def time_remaining(self) -> Optional[float]:
        """Get remaining time before termination."""
        if self.termination_time is None:
            return None
        return max(0, self.termination_period - (time.time() - self.termination_time))

class CheckpointManager:
    """Manager for saving and loading solver checkpoints."""
    def __init__(self, config: Dict[str, Any], run_id: str, timeout_manager: TimeoutManager):
        self.config = config['spot']['checkpointing']
        self.run_id = run_id
        self.timeout_manager = timeout_manager
        self.storage_client = storage.Client()
        self.bucket = self.storage_client.bucket(self.config['gcs_bucket'])
    
    def save_checkpoint(self, solver_state: Dict[str, Any], iteration: int):
        """Save solver state to GCS with timeout."""
        def _save():
            checkpoint = {
                'iteration': iteration,
                'solver_state': solver_state,
                'timestamp': time.time()
            }
            
            # Save locally first
            local_path = f'/tmp/checkpoint_{iteration}.json'
            with open(local_path, 'w') as f:
                json.dump(checkpoint, f)
            
            # Upload to GCS
            gcs_path = self.config['gcs_path'].format(run_id=self.run_id)
            blob = self.bucket.blob(f"{gcs_path}/checkpoint_{iteration}.json")
            blob.upload_from_filename(local_path)
            os.remove(local_path)
            
            # Clean up old checkpoints
            self._cleanup_old_checkpoints()
        
        self.timeout_manager.run_with_timeout(_save, 'checkpoint')
    
    def load_latest_checkpoint(self) -> Optional[Dict[str, Any]]:
        """Load latest checkpoint from GCS with timeout."""
        def _load():
            try:
                gcs_path = self.config['gcs_path'].format(run_id=self.run_id)
                blobs = list(self.bucket.list_blobs(prefix=gcs_path))
                
                if not blobs:
                    return None
                
                # Get latest checkpoint
                latest_blob = max(blobs, key=lambda x: int(x.name.split('_')[-1].split('.')[0]))
                
                # Download checkpoint
                local_path = '/tmp/checkpoint.json'
                latest_blob.download_to_filename(local_path)
                
                with open(local_path, 'r') as f:
                    checkpoint = json.load(f)
                
                os.remove(local_path)
                return checkpoint
            
            except Exception as e:
                print(f"Error loading checkpoint: {e}")
                return None
        
        return self.timeout_manager.run_with_timeout(_load, 'checkpoint')
    
    def _cleanup_old_checkpoints(self):
        """Remove old checkpoints, keeping only the most recent ones."""
        gcs_path = self.config['gcs_path'].format(run_id=self.run_id)
        blobs = list(self.bucket.list_blobs(prefix=gcs_path))
        
        if len(blobs) > self.config['max_to_keep']:
            # Sort by checkpoint number
            sorted_blobs = sorted(blobs, 
                                key=lambda x: int(x.name.split('_')[-1].split('.')[0]),
                                reverse=True)
            
            # Delete old checkpoints
            for blob in sorted_blobs[self.config['max_to_keep']:]:
                blob.delete()

class ORToolsWrapper:
    """Wrapper for Google OR-Tools models with parallel training capabilities."""
    def __init__(self, config: Dict[str, Any], run_id: str = None):
        self.config = config
        self.solver_type = config.get('solver_type', 'cp_sat')
        self.time_limit = config.get('time_limit', 60)
        self.num_workers = config.get('num_workers', 1)
        self.best_solution = None
        self.best_objective = float('inf') if config.get('minimize', True) else float('-inf')
        
        # Initialize timeout manager
        self.timeout_manager = TimeoutManager(config)
        
        # Initialize spot instance handler if enabled
        self.spot_handler = SpotInstanceHandler(config) if config['spot']['enabled'] else None
        
        # Initialize checkpoint manager if enabled
        self.checkpoint_manager = (CheckpointManager(config, run_id, self.timeout_manager) 
                                 if config['spot']['checkpointing']['enabled'] and run_id 
                                 else None)
        
        # Load latest checkpoint if available
        self._load_checkpoint()
    
    def create_solver(self) -> Any:
        """Create appropriate solver based on configuration with timeout."""
        def _create():
            if self.solver_type == 'cp_sat':
                solver = cp_model.CpSolver()
                solver.parameters.max_time_in_seconds = self.config['timeouts']['iteration']
                return solver
            elif self.solver_type == 'mip':
                solver = pywraplp.Solver.CreateSolver('SCIP')
                if solver:
                    solver.SetTimeLimit(self.config['timeouts']['iteration'] * 1000)  # milliseconds
                return solver
            else:
                raise ValueError(f"Unknown solver type: {self.solver_type}")
        
        return self.timeout_manager.run_with_timeout(_create, 'solver_init')
    
    def parallel_solve(self, problem_data: Dict[str, Any]) -> Dict[str, Any]:
        """Solve optimization problem in parallel using data parallelism."""
        try:
            if dist.is_initialized():
                rank = dist.get_rank()
                world_size = dist.get_world_size()
                
                # Partition data across workers
                local_data = self._partition_data(problem_data, rank, world_size)
                
                # Solve local subproblem with spot instance handling and timeouts
                local_solution = self._solve_subproblem_with_timeouts(local_data)
                
                # Gather solutions from all workers
                all_solutions = self._gather_solutions(local_solution)
                
                # Combine solutions (only on rank 0)
                if rank == 0:
                    final_solution = self._combine_solutions(all_solutions)
                    return final_solution
                
                return None
            else:
                # Single worker case
                return self._solve_subproblem_with_timeouts(problem_data)
        
        except TimeoutError as e:
            print(f"Timeout occurred: {e}")
            if self.checkpoint_manager:
                self._save_checkpoint()
            return {'status': 'TIMEOUT', 'solution': self.best_solution, 'objective': self.best_objective}
        
        except Exception as e:
            print(f"Error during solving: {e}")
            if self.checkpoint_manager:
                self._save_checkpoint()
            return {'status': 'ERROR', 'solution': self.best_solution, 'objective': self.best_objective}
    
    def _solve_subproblem_with_timeouts(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Solve subproblem with timeout controls."""
        iteration = 0
        solution = None
        
        while not self.timeout_manager.check_total_runtime():
            try:
                # Check for spot instance termination
                if self.spot_handler and self.spot_handler.should_checkpoint():
                    if self.checkpoint_manager:
                        self._save_checkpoint()
                    break
                
                # Solve for a limited time
                solution = self._solve_subproblem(data)
                
                # Check for improvement timeout
                if solution and solution['status'] in [cp_model.OPTIMAL, pywraplp.Solver.OPTIMAL]:
                    if self.timeout_manager.check_improvement_timeout(solution['objective']):
                        print("Stopping due to no improvement timeout")
                        break
                
                # Save checkpoint if enabled
                if (self.checkpoint_manager and 
                    iteration % self.config['spot']['checkpointing']['frequency'] == 0):
                    self._save_checkpoint()
                
                iteration += 1
                
                if solution['status'] in [cp_model.OPTIMAL, pywraplp.Solver.OPTIMAL]:
                    break
                
            except TimeoutError as e:
                print(f"Iteration timeout: {e}")
                if self.checkpoint_manager:
                    self._save_checkpoint()
                break
            
            except Exception as e:
                print(f"Error during solving: {e}")
                if self.checkpoint_manager:
                    self._save_checkpoint()
                break
        
        return solution or {'status': 'TIMEOUT', 'solution': self.best_solution, 'objective': self.best_objective}
    
    def _save_checkpoint(self):
        """Save current solver state."""
        if not self.checkpoint_manager:
            return
        
        solver_state = {
            'best_solution': self.best_solution,
            'best_objective': self.best_objective,
            'solver_type': self.solver_type,
            'time_limit': self.time_limit
        }
        
        self.checkpoint_manager.save_checkpoint(solver_state, int(time.time()))
    
    def _load_checkpoint(self):
        """Load solver state from checkpoint."""
        if not self.checkpoint_manager:
            return
        
        checkpoint = self.checkpoint_manager.load_latest_checkpoint()
        if checkpoint:
            solver_state = checkpoint['solver_state']
            self.best_solution = solver_state['best_solution']
            self.best_objective = solver_state['best_objective']
            print(f"Restored from checkpoint at iteration {checkpoint['iteration']}")
    
    def _partition_data(self, data: Dict[str, Any], rank: int, world_size: int) -> Dict[str, Any]:
        """Partition problem data across workers."""
        partitioned_data = {}
        
        for key, value in data.items():
            if isinstance(value, (np.ndarray, list)):
                # Partition array-like data
                if isinstance(value, list):
                    value = np.array(value)
                chunk_size = len(value) // world_size
                start_idx = rank * chunk_size
                end_idx = start_idx + chunk_size if rank < world_size - 1 else len(value)
                partitioned_data[key] = value[start_idx:end_idx]
            else:
                # Copy non-array data as is
                partitioned_data[key] = value
        
        return partitioned_data
    
    def _solve_subproblem(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Solve local subproblem using appropriate solver."""
        if self.solver_type == 'cp_sat':
            return self._solve_cp_sat(data)
        elif self.solver_type == 'mip':
            return self._solve_mip(data)
        else:
            raise ValueError(f"Unknown solver type: {self.solver_type}")
    
    def _solve_cp_sat(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Solve constraint programming problem using CP-SAT solver."""
        model = cp_model.CpModel()
        
        # Create variables based on data
        variables = self._create_cp_variables(model, data)
        
        # Add constraints
        self._add_cp_constraints(model, variables, data)
        
        # Set objective
        self._set_cp_objective(model, variables, data)
        
        # Solve
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit
        status = solver.Solve(model)
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            solution = self._extract_cp_solution(solver, variables)
            objective = solver.ObjectiveValue()
            return {'status': status, 'solution': solution, 'objective': objective}
        
        return {'status': status, 'solution': None, 'objective': None}
    
    def _solve_mip(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Solve mixed integer programming problem using SCIP solver."""
        solver = pywraplp.Solver.CreateSolver('SCIP')
        if not solver:
            return {'status': 'ERROR', 'solution': None, 'objective': None}
        
        # Create variables based on data
        variables = self._create_mip_variables(solver, data)
        
        # Add constraints
        self._add_mip_constraints(solver, variables, data)
        
        # Set objective
        self._set_mip_objective(solver, variables, data)
        
        # Solve
        solver.SetTimeLimit(self.time_limit * 1000)  # Convert to milliseconds
        status = solver.Solve()
        
        if status == pywraplp.Solver.OPTIMAL or status == pywraplp.Solver.FEASIBLE:
            solution = self._extract_mip_solution(solver, variables)
            objective = solver.Objective().Value()
            return {'status': status, 'solution': solution, 'objective': objective}
        
        return {'status': status, 'solution': None, 'objective': None}
    
    def _gather_solutions(self, local_solution: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Gather solutions from all workers."""
        if not dist.is_initialized():
            return [local_solution]
        
        world_size = dist.get_world_size()
        gathered_solutions = [None] * world_size
        
        # Gather solutions to rank 0
        dist.gather_object(local_solution, gathered_solutions if dist.get_rank() == 0 else None)
        
        return gathered_solutions
    
    def _combine_solutions(self, solutions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Combine solutions from multiple workers (implemented by subclasses)."""
        raise NotImplementedError("Subclasses must implement _combine_solutions")

class RoutingOptimizer(ORToolsWrapper):
    """Specialized optimizer for vehicle routing problems."""
    def _create_cp_variables(self, model: cp_model.CpModel, data: Dict[str, Any]) -> Dict[str, Any]:
        num_vehicles = data['num_vehicles']
        num_locations = len(data['distances'])
        
        # Create variables for each vehicle's route
        routes = {}
        for v in range(num_vehicles):
            for i in range(num_locations):
                for j in range(num_locations):
                    if i != j:
                        routes[(v, i, j)] = model.NewBoolVar(f'route_{v}_{i}_{j}')
        
        return {'routes': routes}
    
    def _add_cp_constraints(self, model: cp_model.CpModel, variables: Dict[str, Any], data: Dict[str, Any]):
        routes = variables['routes']
        num_vehicles = data['num_vehicles']
        num_locations = len(data['distances'])
        
        # Each location must be visited exactly once
        for j in range(1, num_locations):
            model.Add(sum(routes[(v, i, j)] 
                         for v in range(num_vehicles) 
                         for i in range(num_locations) 
                         if i != j) == 1)
        
        # Each vehicle must leave the depot at most once
        for v in range(num_vehicles):
            model.Add(sum(routes[(v, 0, j)] 
                         for j in range(1, num_locations)) <= 1)
        
        # Flow conservation
        for v in range(num_vehicles):
            for h in range(num_locations):
                model.Add(sum(routes[(v, i, h)] for i in range(num_locations) if i != h) ==
                         sum(routes[(v, h, j)] for j in range(num_locations) if j != h))
    
    def _set_cp_objective(self, model: cp_model.CpModel, variables: Dict[str, Any], data: Dict[str, Any]):
        routes = variables['routes']
        distances = data['distances']
        
        # Minimize total distance
        model.Minimize(sum(routes[(v, i, j)] * distances[i][j]
                         for v in range(data['num_vehicles'])
                         for i in range(len(distances))
                         for j in range(len(distances))
                         if i != j))
    
    def _combine_solutions(self, solutions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Combine routing solutions by selecting the best one."""
        best_solution = None
        best_objective = float('inf')
        
        for solution in solutions:
            if solution and solution['status'] in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
                if solution['objective'] < best_objective:
                    best_solution = solution['solution']
                    best_objective = solution['objective']
        
        return {'status': cp_model.OPTIMAL if best_solution else cp_model.INFEASIBLE,
                'solution': best_solution,
                'objective': best_objective}

class SchedulingOptimizer(ORToolsWrapper):
    """Specialized optimizer for job scheduling problems."""
    def _create_mip_variables(self, solver: pywraplp.Solver, data: Dict[str, Any]) -> Dict[str, Any]:
        num_jobs = len(data['processing_times'])
        num_machines = data['num_machines']
        horizon = sum(data['processing_times'])
        
        # Start time variables for each job
        start_times = {}
        for j in range(num_jobs):
            start_times[j] = solver.NumVar(0, horizon, f'start_{j}')
        
        # Machine assignment variables
        assignments = {}
        for j in range(num_jobs):
            for m in range(num_machines):
                assignments[(j, m)] = solver.BoolVar(f'assign_{j}_{m}')
        
        return {'start_times': start_times, 'assignments': assignments}
    
    def _add_mip_constraints(self, solver: pywraplp.Solver, variables: Dict[str, Any], data: Dict[str, Any]):
        start_times = variables['start_times']
        assignments = variables['assignments']
        processing_times = data['processing_times']
        num_jobs = len(processing_times)
        num_machines = data['num_machines']
        
        # Each job must be assigned to exactly one machine
        for j in range(num_jobs):
            solver.Add(sum(assignments[(j, m)] for m in range(num_machines)) == 1)
        
        # Non-overlapping constraints
        big_m = sum(processing_times)
        for m in range(num_machines):
            for j1 in range(num_jobs):
                for j2 in range(j1 + 1, num_jobs):
                    solver.Add(start_times[j1] + processing_times[j1] <= start_times[j2] + 
                             big_m * (3 - assignments[(j1, m)] - assignments[(j2, m)] - 
                                    solver.BoolVar(f'order_{j1}_{j2}')))
                    solver.Add(start_times[j2] + processing_times[j2] <= start_times[j1] + 
                             big_m * (2 - assignments[(j1, m)] - assignments[(j2, m)] + 
                                    solver.BoolVar(f'order_{j1}_{j2}')))
    
    def _set_mip_objective(self, solver: pywraplp.Solver, variables: Dict[str, Any], data: Dict[str, Any]):
        start_times = variables['start_times']
        processing_times = data['processing_times']
        
        # Minimize makespan
        makespan = solver.NumVar(0, solver.infinity(), 'makespan')
        for j in range(len(processing_times)):
            solver.Add(start_times[j] + processing_times[j] <= makespan)
        solver.Minimize(makespan)
    
    def _combine_solutions(self, solutions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Combine scheduling solutions by selecting the best makespan."""
        best_solution = None
        best_objective = float('inf')
        
        for solution in solutions:
            if solution and solution['status'] in [pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE]:
                if solution['objective'] < best_objective:
                    best_solution = solution['solution']
                    best_objective = solution['objective']
        
        return {'status': pywraplp.Solver.OPTIMAL if best_solution else pywraplp.Solver.NOT_SOLVED,
                'solution': best_solution,
                'objective': best_objective} 