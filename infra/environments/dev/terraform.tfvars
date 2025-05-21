project_id         = "your-project-id"  # Your GCP project ID
environment        = "dev"
region            = "us-central1"
domain            = "your-domain.com"
cluster_name      = "developer-platform"

mlflow_config = {
  version           = "2.10.2"
  db_version        = "15.5"
  artifact_bucket   = "mlflow-artifacts"
  backup_bucket     = "mlflow-backups"
  retention_days    = 30
  db_storage_size   = "50Gi"
}

# Resource limits
mlflow_resources = {
  server = {
    cpu_request    = "1"
    cpu_limit      = "2"
    memory_request = "1Gi"
    memory_limit   = "2Gi"
  }
  database = {
    cpu_request    = "2"
    cpu_limit      = "4"
    memory_request = "4Gi"
    memory_limit   = "8Gi"
  }
} 