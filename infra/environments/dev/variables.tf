variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "region" {
  description = "The GCP region to deploy to"
  type        = string
  default     = "us-central1"
}

variable "domain" {
  description = "The domain name for the platform"
  type        = string
}

variable "cluster_name" {
  description = "The name of the GKE cluster"
  type        = string
}

variable "mlflow_config" {
  description = "MLflow configuration settings"
  type = object({
    version           = string
    db_version        = string
    artifact_bucket   = string
    backup_bucket     = string
    retention_days    = number
    db_storage_size   = string
  })
}

variable "mlflow_resources" {
  description = "Resource limits for MLflow components"
  type = object({
    server = object({
      cpu_request    = string
      cpu_limit      = string
      memory_request = string
      memory_limit   = string
    })
    database = object({
      cpu_request    = string
      cpu_limit      = string
      memory_request = string
      memory_limit   = string
    })
  })
}

variable "alert_email" {
  description = "Email address for monitoring alerts"
  type        = string
} 