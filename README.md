# Developer Platform

A production-grade developer platform running on GKE that provides on-demand VSCode and Jupyter environments.

## 🎯 Features

- On-demand VSCode (code-server) and Jupyter runtime environments
- Per-user pod creation in shared namespace
- Configurable runtime resources (CPU, memory, GPU)
- Multi-layer versioning and backup:
  - GCSFuse-based file versioning
  - Daily automated PVC backups
  - Git-based workspace versioning
- GitOps-based deployments with ArgoCD
- CI/CD automation with GitHub Actions
- GCP-native infrastructure with Terraform
- Intelligent storage lifecycle management
- Comprehensive monitoring and logging
- Enhanced Security Features:
  - VPC Service Controls for data exfiltration prevention
  - Container vulnerability scanning
  - Granular IAM roles and permissions
  - Cost management and budget controls
  - Comprehensive audit logging
  - Security event monitoring and alerting

## 🏗️ Architecture

### Core Components

- **Cloud Infrastructure**: Google Cloud Platform (GCP)
- **Container Orchestration**: Google Kubernetes Engine (GKE)
- **Container Registry**: Google Artifact Registry
- **GitOps**: ArgoCD
- **CI/CD**: GitHub Actions
- **Authentication**: OIDC (configurable with Keycloak/Google/GitHub)
- **Pod Management**: JupyterHub + KubeSpawner
- **Runtime Environments**: VSCode (code-server) + JupyterLab
- **Storage**: Per-user PVC, optional GCSFuse integration
- **Monitoring**: Prometheus + Grafana

### Resource Profiles

Available runtime configurations:
- **standard**: 2 CPU, 8GB RAM
- **highmem**: 4 CPU, 16GB RAM
- **ml-gpu**: 8 CPU, 32GB RAM, 1 NVIDIA GPU

## 🚀 Getting Started

### Prerequisites

1. GCP Project with required permissions:
   - Project Owner or Editor role
   - Ability to enable APIs
   - Ability to create service accounts

2. GitHub repository secrets:
   - `BOOTSTRAP_SA_KEY`: Service account key with Owner/Editor permissions (for bootstrap only)
   - `ARGOCD_ADMIN_PASSWORD`: Desired admin password for ArgoCD

3. Domain name with ability to configure DNS records

### Initial Setup

1. Fork/clone the repository:
   ```bash
   git clone https://github.com/youorg/developer-platform.git
   cd developer-platform
   ```

2. Configure GitHub repository secrets:
   - Go to Settings > Secrets and Variables > Actions
   - Add the required secrets mentioned above

3. Run the bootstrap workflow:
   - Go to Actions > Bootstrap Infrastructure
   - Click "Run workflow"
   - Fill in the required parameters:
     - GCP Project ID
     - Region (default: us-central1)
     - Domain name
     - Environment (prod/staging/dev)
   - Click "Run workflow"

4. Wait for the bootstrap process to complete (~15-20 minutes)

5. Configure DNS records:
   - Add A/CNAME records for:
     - `argocd.your-domain.com`
     - `jupyter.your-domain.com`
     - `grafana.your-domain.com`

### Post-Bootstrap

After the bootstrap process completes:

1. Access ArgoCD:
   - URL: `https://argocd.your-domain.com`
   - Username: `admin`
   - Password: Value of `ARGOCD_ADMIN_PASSWORD` secret

2. Access JupyterHub:
   - URL: `https://jupyter.your-domain.com`
   - Authentication through configured OIDC provider

3. Access Grafana:
   - URL: `https://grafana.your-domain.com`
   - Default admin credentials in ArgoCD secrets

## 📁 Repository Structure

```
.
├── infra/                  # Terraform modules and environments
│   ├── modules/           # Reusable Terraform modules
│   └── environments/      # Environment-specific configurations
├── k8s/                   # Kubernetes manifests
│   ├── base/             # Base Kustomize configurations
│   └── overlays/         # Environment-specific overlays
├── runtime/              # Runtime configurations
│   ├── vscode/          # VSCode specific configurations
│   ├── jupyter/         # Jupyter specific configurations
│   └── runtime-configs/ # Resource profiles and settings
├── runtime-image/        # Combined VSCode + Jupyter image
├── jupyterhub/          # JupyterHub configurations
├── scripts/             # Utility scripts
└── .github/workflows/   # CI/CD pipelines
```

## 🔧 Configuration

### Runtime Environments

Users can select from predefined resource profiles in `runtime/runtime-configs/`:
- Modify `profiles.yaml` to add/update resource configurations
- Update node selectors and tolerations as needed
- Configure custom environment variables and mounts

### Authentication

The platform uses Google OIDC for authentication and authorization:

1. **OIDC Configuration**:
   - Integration with Google Identity Platform
   - Group-based access control
   - Supported scopes: OpenID, email, profile, and groups
   - Configuration in `k8s/base/auth/oidc-config.yaml`

2. **User Groups**:
   - Regular users: `developer-platform-users@your-domain.com`
   - Administrators: `developer-platform-admins@your-domain.com`
   - Group membership managed through Google Workspace

3. **RBAC Permissions**:
   Regular Users (`jupyter-user` role):
   - View and access their own pods
   - View pod logs
   - Manage their PVC storage
   - Execute commands in pods

   Administrators (`jupyter-admin` role):
   - Full pod management
   - Service and deployment control
   - ConfigMap and Secret management
   - Storage management
   - User session management

4. **Setup Steps**:
   a. Create OAuth Client in GCP Console:
      - Go to APIs & Services > Credentials
      - Create OAuth 2.0 Client ID
      - Add authorized redirect URI: `https://jupyter.your-domain.com/hub/oauth_callback`
   
   b. Update Configuration:
      - Copy `k8s/base/oauth.env.example` to `k8s/base/oauth.env`
      - Add your OAuth client credentials
      - Update domain and groups in `k8s/base/auth.env`
   
   c. Create Google Groups:
      - Create user and admin groups in Google Workspace
      - Add users to appropriate groups
      - Ensure groups are visible to the OAuth client

5. **Security Considerations**:
   - OAuth credentials managed as Kubernetes secrets
   - RBAC policies enforce least-privilege access
   - Group membership required for platform access
   - Regular audit logging of authentication events

### Storage

Each user gets isolated storage through:
- Persistent Volume Claims (PVC) with versioning:
  1. **GCS-native Versioning** (Default):
     - Automatic file versioning through Google Cloud Storage
     - 30-day minimum retention period
     - 10 versions per file maximum
     - Version history accessible via `.versions/` directory
     - Automatic lifecycle management:
       - 0-30 days: Standard Storage
       - 31-90 days: Nearline Storage
       - 91-365 days: Coldline Storage
       - 365+ days: Automatic cleanup of old versions
  2. **Git-based Versioning**:
     - Automatic Git initialization in workspaces
     - Pre-commit hooks for code formatting
     - Special handling for Jupyter notebooks via nbdime
     - Git LFS support for large files

Storage Features:
- 10GB base storage per user
- Automatic version history
- Time-based version naming
- Intelligent storage tiering
- Built-in data retention policies

### 🔒 Security

The platform implements multiple layers of security controls:

1. **VPC Service Controls**:
   - Network-level isolation of resources
   - Prevention of data exfiltration
   - Granular access controls for APIs
   - Perimeter security for sensitive data

2. **Container Security**:
   - Automated vulnerability scanning
   - Binary Authorization policies
   - Container image signing and verification
   - Preemptible nodes for non-critical workloads

3. **Identity and Access Management**:
   - Custom IAM roles with least privilege
   - Role-based access control (RBAC)
   - Service account key rotation
   - Regular access reviews

4. **Audit and Compliance**:
   - Comprehensive audit logging
   - 365-day log retention
   - Security event monitoring
   - Real-time alerting for:
     - Critical security events
     - IAM policy changes
     - GKE security events

5. **Cost Controls and Resource Management**:
   - Budget alerts at 50%, 80%, and 90% thresholds
   - Cost allocation tagging
   - Resource usage monitoring
   - Automated resource cleanup

6. **Data Protection**:
   - Encryption at rest with Cloud KMS
   - TLS encryption in transit
   - Regular security assessments
   - Automated backup and recovery

7. **Security Monitoring**:
   - Real-time security event notifications
   - Integration with security tools
   - Custom security dashboards
   - Incident response automation

8. **Compliance Features**:
   - Audit trails for all changes
   - Policy enforcement
   - Regular compliance reporting
   - Data residency controls

### Security Configuration

1. **VPC Service Controls Setup**:
   ```hcl
   # Example configuration in infra/environments/[env]/main.tf
   variable "authorized_ip_ranges" {
     description = "List of authorized IP ranges for VPC Service Controls"
     type        = list(string)
   }

   variable "security_team_email" {
     description = "Email for security notifications"
     type        = string
   }
   ```

2. **Budget Controls**:
   ```hcl
   # Configure in infra/environments/[env]/main.tf
   variable "monthly_budget_amount" {
     description = "Monthly budget amount in USD"
     type        = number
     default     = 1000
   }
   ```

3. **Security Monitoring**:
   - Configure email notifications in `infra/environments/[env]/main.tf`
   - Set up custom alert policies
   - Define audit logging parameters

4. **Required Variables**:
   ```bash
   # Required environment variables for security features
   export TF_VAR_billing_account_id="YOUR_BILLING_ACCOUNT"
   export TF_VAR_security_team_email="security@your-domain.com"
   export TF_VAR_cost_center="COST_CENTER_ID"
   export TF_VAR_business_unit="BUSINESS_UNIT"
   ```

5. **Security Best Practices**:
   - Regularly rotate service account keys
   - Monitor security event logs
   - Review access permissions periodically
   - Keep container images updated
   - Enable vulnerability scanning
   - Configure budget alerts

## 📊 Monitoring

Access monitoring dashboards:
1. Prometheus metrics: `http://prometheus.<your-domain>`
2. Grafana dashboards: `http://grafana.<your-domain>`

Default dashboards include:
- Cluster health metrics
- User resource utilization
- Pod status and events
- Storage metrics

## 🔄 Version Control & Recovery

### Accessing Version History

1. **GCS Versions** (Default Storage):
   ```bash
   # List versions in the .versions directory
   ls .versions/
   
   # Access specific version by timestamp
   cp .versions/myfile_2024-03-15_14-30-00 ./myfile
   ```

2. **Git Version Control**:
   - Standard Git commands work in your workspace
   - Visual diff support for Jupyter notebooks
   - Large files automatically handled by Git LFS
   ```bash
   # View notebook changes
   nbdiff notebook.ipynb
   
   # Commit changes
   git add .
   git commit -m "Your message"
   ```

### Storage Lifecycle

- Files retain at least 30 days of history
- Automatic tiering for cost optimization:
  - 0-30 days: Standard Storage (fast access)
  - 31-90 days: Nearline Storage (cost-effective)
  - 91-365 days: Coldline Storage (archival)
  - Versions older than 365 days are automatically cleaned up

### MLflow Integration

The platform includes a fully managed MLflow tracking server with the following features:

#### Core Components

- **MLflow Tracking Server** (v2.10.2):
  - Centralized experiment tracking
  - Model registry and versioning
  - Artifact storage in Google Cloud Storage
  - Shared authentication with JupyterHub
  - Automatic environment configuration

- **Database Backend**:
  - PostgreSQL 15.5 for experiment tracking
  - Daily automated backups to GCS
  - 30-day backup retention
  - High-availability configuration

- **Artifact Storage**:
  - GCS-based artifact storage
  - Intelligent lifecycle management:
    - 0-30 days: Standard Storage
    - 31-90 days: Nearline Storage
    - 91-365 days: Coldline Storage
    - 365+ days: Automatic cleanup

#### Usage

MLflow is pre-configured in all JupyterHub and VSCode environments:

1. **Access MLflow UI**:
   - URL: `https://mlflow.your-domain.com`
   - Authentication: Same as JupyterHub login

2. **Environment Integration**:
   - Automatic configuration in all environments
   - Pre-installed MLflow Python package
   - Environment variables pre-configured
   - Example notebooks in JupyterHub launcher

3. **Using MLflow**:
   ```python
   import mlflow
   
   # Tracking is automatically configured
   mlflow.start_run()
   mlflow.log_param("param1", value1)
   mlflow.log_metric("metric1", value1)
   mlflow.end_run()
   ```

#### Backup and Recovery

1. **Database Backups**:
   - Automated daily backups at 1 AM
   - Stored in GCS: `gs://<bucket>/mlflow/backups/`
   - 30-day retention policy
   - Point-in-time recovery capability

2. **Artifact Management**:
   - Versioned storage in GCS
   - Automatic lifecycle policies
   - Cost-optimized storage classes
   - Configurable retention periods

#### Security

- Shared authentication with JupyterHub
- RBAC-based access control
- Encrypted data at rest
- Secure credential management
- TLS encryption in transit

#### Resource Limits

- MLflow Server:
  - CPU: 1 core (limit: 2 cores)
  - Memory: 1GB (limit: 2GB)
  - Storage: Based on usage

- PostgreSQL:
  - CPU: 2 cores (limit: 4 cores)
  - Memory: 4GB (limit: 8GB)
  - Storage: 50GB with auto-expand

## 🔄 Recovery Options

1. **Self-service Recovery**:
   - Browse versions through `.versions/` directory
   - Use Git history for code versioning
   - Access GCS versions through Cloud Console

2. **Admin Recovery**:
   - Direct GCS bucket access
   - Object version management
   - Retention policy adjustments

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.
