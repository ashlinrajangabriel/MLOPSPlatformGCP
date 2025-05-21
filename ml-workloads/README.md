# ML Workloads Platform

A comprehensive platform for managing machine learning workloads with support for distributed training, optimization problems, and production deployments.

## Features

### 1. Machine Learning Components

#### Training Infrastructure
- Distributed PyTorch training with DDP support
- MLflow integration for experiment tracking
- GCS checkpoint storage and loading
- Early stopping and model saving
- Custom metrics tracking
- Spot instance support with automatic checkpointing
- Comprehensive timeout management

#### Inference Services
- FastAPI async service for high throughput
- Flask sync service for simpler deployments
- Model versioning and caching
- Health checks and monitoring
- Canary deployment support
- Batch inference capabilities

#### Optimization Tools
- Google OR-Tools integration with parallel solving
- Support for routing and scheduling problems
- Distributed optimization with checkpointing
- Spot instance compatibility
- Multi-level timeout controls
- Solution visualization

### 2. Project Structure

```
ml-workloads/
├── usecase_template/
│   ├── training/
│   │   ├── utils/
│   │   │   ├── models.py       # PyTorch models
│   │   │   ├── or_models.py    # OR-Tools models
│   │   │   ├── metrics.py      # Metrics tracking
│   │   │   └── data.py         # Data loading
│   │   └── train.py            # Training script
│   ├── inference/
│   │   ├── sync/               # Synchronous inference
│   │   └── async/              # Asynchronous inference
│   ├── preprocessing/
│   │   └── preprocess.py       # Data preprocessing
│   └── config/
│       ├── training.yaml       # Training configuration
│       ├── inference.yaml      # Inference configuration
│       ├── or_tools.yaml       # Optimization configuration
│       └── preprocessing.yaml  # Preprocessing configuration
├── base/
│   ├── docker/
│   │   ├── Dockerfile.base     # Base Docker image
│   │   └── entrypoint.sh       # Container entrypoint
│   └── k8s/
│       ├── training-job.yaml   # Training Kubernetes job
│       └── inference-deployment.yaml  # Inference deployment
└── runtime/
    └── runtime-configs/        # Runtime configurations
```

### 3. Configuration System

#### Training Configuration
```yaml
training:
  distributed: true
  num_epochs: 100
  batch_size: 32
  checkpointing:
    enabled: true
    frequency: 5
```

#### OR-Tools Configuration
```yaml
solver:
  type: "cp_sat"
  time_limit: 60
timeouts:
  total_runtime: 3600
  iteration: 300
spot:
  enabled: true
  checkpointing:
    enabled: true
```

#### Inference Configuration
```yaml
service:
  max_workers: 4
  batch_size: 32
monitoring:
  enable_metrics: true
```

### 5. Feature Store Integration

The platform integrates with Feast feature store for managing ML features:

#### Components
- BigQuery offline store for historical features
- Cloud Datastore online store for real-time serving
- GCS-based registry for feature definitions
- Python feature server for online serving
- Airflow-based feature computation and materialization

#### Security
- Google Cloud authentication
- RBAC support
- CMEK encryption for sensitive data
- Secure feature access controls

#### Usage
1. Feature Definition
```python
from feast import Entity, Feature, FeatureView, BigQuerySource
# Define features in feature_store/features/
```

2. Training Data Retrieval
```python
from feast import FeatureStore
store = FeatureStore(repo_path="feature_store")
features = store.get_historical_features(
    entity_df=entities,
    features=[...]
).to_df()
```

3. Online Inference
```python
online_features = store.get_online_features(
    features=[...],
    entity_rows=[{"id": "model1"}]
).to_dict()
```

4. Feature Computation Pipeline
```bash
# View Airflow DAG
airflow dags list
airflow dags trigger feature_store_pipeline
```

#### Development Workflow
1. Define features in `feature_store/features/`
2. Test locally using Jupyter/VSCode
3. Deploy using Airflow DAGs
4. Monitor using MLflow integration

## Usage Examples

### 1. Training Models

#### Standard Training
```bash
python -m training.train --config config/training.yaml
```

#### Distributed Training
```bash
python -m torch.distributed.launch --nproc_per_node=4 \
  training.train --config config/training.yaml
```

### 2. Optimization Problems

#### Vehicle Routing
```python
from training.utils.or_models import RoutingOptimizer

optimizer = RoutingOptimizer(config)
solution = optimizer.parallel_solve(data)
```

#### Job Scheduling
```python
from training.utils.or_models import SchedulingOptimizer

optimizer = SchedulingOptimizer(config)
solution = optimizer.parallel_solve(data)
```

### 3. Inference Services

#### Start Sync Service
```bash
python -m inference.sync.app --config config/inference.yaml
```

#### Start Async Service
```bash
python -m inference.async.app --config config/inference.yaml
```

## Deployment

### 1. Local Development
```bash
# Build Docker image
docker build -t ml-workload:latest -f base/docker/Dockerfile.base .

# Run training
docker run ml-workload:latest train --config config/training.yaml

# Run inference
docker run -p 8000:8000 ml-workload:latest serve --config config/inference.yaml
```

### 2. Kubernetes Deployment
```bash
# Deploy training job
kubectl apply -f base/k8s/training-job.yaml

# Deploy inference service
kubectl apply -f base/k8s/inference-deployment.yaml
```

## Key Features Deep Dive

### 1. Spot Instance Support
- Automatic termination detection
- Graceful shutdown handling
- State checkpointing to GCS
- Automatic recovery on restart
- Configurable termination grace period

### 2. Timeout Management
- Multiple timeout levels:
  - Total runtime
  - Per iteration
  - Improvement threshold
  - Operation-specific
- Graceful timeout handling
- State preservation
- Configurable grace periods

### 3. Distributed Training
- Data parallel training (DDP)
- Multi-GPU support
- Spot instance compatibility
- Checkpointing and recovery
- MLflow integration

### 4. Monitoring & Logging
- MLflow experiment tracking
- Custom metrics logging
- Health check endpoints
- Resource monitoring
- Prediction logging

## Infrastructure Requirements

### Compute Resources
- CPU: 4+ cores recommended
- Memory: 8GB+ recommended
- GPU: Optional, NVIDIA GPU for training
- Storage: GCS bucket for artifacts

### Cloud Services
- Google Cloud Storage
- Kubernetes cluster (GKE)
- MLflow tracking server
- Monitoring stack (optional)

## Security Considerations

### Authentication
- GCP service account for GCS access
- MLflow authentication
- API authentication for inference

### Data Protection
- Encrypted storage
- Secure communication
- Access control

## Best Practices

### Development
1. Use version control for configurations
2. Test with small datasets first
3. Monitor resource usage
4. Use spot instances for cost optimization
5. Implement proper error handling

### Deployment
1. Use canary deployments
2. Monitor service health
3. Set up alerts
4. Regular backups
5. Resource quota management

## Troubleshooting

### Common Issues
1. Out of memory errors
2. Timeout issues
3. Spot instance termination
4. Configuration errors

### Solutions
1. Adjust batch sizes
2. Configure appropriate timeouts
3. Enable checkpointing
4. Validate configurations

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes
4. Submit pull request

## License

MIT License - See LICENSE file for details

### 6. Security & Networking

#### Network Architecture
```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Feature    │     │   Airflow    │     │    MLflow    │
│   Server     │     │   Workers    │     │   Tracking   │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                     │
       │                    │                     │
┌──────┴───────┐     ┌─────┴──────┐      ┌──────┴───────┐
│    GCS       │     │  Datastore  │      │  Prometheus  │
│  (Offline)   │     │  (Online)   │      │ Monitoring   │
└──────────────┘     └────────────┘       └──────────────┘
```

#### Network Policies
1. Feature Server:
   - Ingress:
     * ML workload pods (port 8666)
     * Platform namespaces
     * Prometheus monitoring (port 9090)
   - Egress:
     * Cloud Datastore (10.0.0.0/8)
     * GCS (172.16.0.0/12)
     * MLflow tracking (port 5000)

2. Airflow Workers:
   - Ingress:
     * Platform components (port 8080)
     * Prometheus monitoring (port 9090)
   - Egress:
     * Feature server (port 8666)
     * GCS and Datastore
     * MLflow tracking (port 5000)

3. MLflow:
   - Ingress:
     * Platform components (port 5000)
     * Prometheus monitoring (port 9090)
   - Egress:
     * GCS for artifact storage

#### Security Groups & IAM
1. Service Accounts:
   - Feature Server:
     * GCS read-only access
     * Datastore user access
     * KMS encryption/decryption
   - Airflow:
     * GCS admin access
     * Datastore user access
     * KMS encryption/decryption
   - MLflow:
     * GCS admin for artifacts

2. Pod Security:
   - Non-root execution
   - Read-only filesystem
   - Dropped capabilities
   - No privilege escalation

3. RBAC Policies:
   - Namespace-scoped roles
   - Least privilege access
   - Resource-specific permissions

#### Data Protection
1. At Rest:
   - CMEK encryption for GCS
   - Datastore encryption
   - KMS key management

2. In Transit:
   - TLS 1.3 enforcement
   - Internal traffic encryption
   - Service mesh mTLS (optional)

3. Access Control:
   - Workload Identity
   - Service account keys
   - IP-based restrictions

#### Monitoring & Auditing
1. Metrics:
   - Prometheus endpoints
   - Custom metrics
   - SLO monitoring

2. Logging:
   - Cloud Logging integration
   - Audit trails
   - Access logs

3. Alerts:
   - Security violations
   - Performance issues
   - Resource utilization

#### Security Best Practices
1. Development:
   - Regular security updates
   - Dependency scanning
   - Container scanning

2. Deployment:
   - Immutable tags
   - Vulnerability scanning
   - Configuration validation

3. Operations:
   - Access reviews
   - Rotation policies
   - Incident response 