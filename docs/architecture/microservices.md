# MLflow Solution Microservices Architecture

## Overview
The MLflow deployment consists of several microservices working together to provide a robust and secure machine learning experiment tracking system. Each service is containerized and deployed on Google Kubernetes Engine (GKE).

## Core Services

### 1. MLflow Tracking Server
The main service that handles experiment tracking, model registration, and artifact management.

**Components:**
- **Main Container**: MLflow Server
  - Image: `ghcr.io/mlflow/mlflow`
  - Purpose: Handles all MLflow API requests and web UI
  - Configurations:
    - TLS encryption enabled
    - PostgreSQL backend for metadata
    - Google Cloud Storage for artifact storage

- **Sidecar Container**: Cloud SQL Auth Proxy
  - Image: `gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.1.0`
  - Purpose: Secure connection to Cloud SQL
  - Features:
    - IAM authentication
    - Encrypted connection
    - Automatic credential management

**Kubernetes Resources:**
```hcl
kubernetes_deployment.mlflow
kubernetes_service.mlflow
```

### 2. PostgreSQL Database
Stateful service that stores MLflow metadata.

**Components:**
- **Database Container**: PostgreSQL
  - Purpose: Metadata storage
  - Features:
    - Persistent storage
    - Health monitoring
    - Automatic backups
    - Encryption at rest

**Kubernetes Resources:**
```hcl
kubernetes_stateful_set.mlflow_db
kubernetes_service.mlflow_db
kubernetes_persistent_volume_claim.mlflow_db
```

## Development Environment Services

### 1. VS Code Server
The VS Code development environment service provides browser-based access to VS Code.

**Components:**
- **VS Code Server Container**
  - Purpose: Remote development environment
  - Features:
    - Browser-based VS Code IDE
    - Git integration
    - Extension support
    - Terminal access
    - Multi-language support
    - Collaborative features

### 2. Jupyter Server
Interactive notebook environment for data science and ML development.

**Components:**
- **Jupyter Server Container**
  - Purpose: Interactive Python notebook environment
  - Features:
    - Interactive code execution
    - Markdown documentation
    - Visualization support
    - MLflow integration
    - Package management
    - GPU support (when configured)

**Integration with MLflow:**
- Direct tracking of experiments from notebooks
- Model logging and versioning
- Artifact management
- Parameter tracking
- Metric logging

## Supporting Cloud Services

### 1. Google Cloud Storage
- Purpose: Artifact storage
- Features:
  - Versioning enabled
  - Lifecycle management
  - Customer-managed encryption keys
  - Uniform bucket-level access

### 2. Cloud SQL
- Purpose: Production-grade database service
- Features:
  - Automated backups
  - High availability
  - Encryption at rest
  - Private networking
  - IAM authentication

## Service Communication

### Internal Communication
- MLflow Server → PostgreSQL: Via Cloud SQL Auth Proxy (secure tunnel)
- MLflow Server → GCS: Via IAM authentication and service account
- Jupyter → MLflow Server: Direct HTTP(S) communication
- VS Code → MLflow Server: Direct HTTP(S) communication
- All internal communication is encrypted and authenticated

### External Access
- Client → MLflow Server: Via HTTPS (TLS)
- Authentication: IAM-based
- Network Security: Private GKE cluster with authorized networks

## Monitoring & Logging

Each service is monitored through:
1. Cloud Monitoring dashboards
2. Custom alert policies
3. Centralized logging
4. Health checks and probes

## Security Features

1. All services use encryption at rest
2. TLS encryption for in-transit data
3. IAM-based authentication
4. Private networking
5. Regular key rotation
6. Audit logging enabled

## High Availability

1. Kubernetes deployment ensures service availability
2. Cloud SQL provides database redundancy
3. GCS ensures artifact durability
4. Health checks and automatic recovery 