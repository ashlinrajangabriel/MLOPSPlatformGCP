output "cluster_name" {
  description = "The name of the GKE cluster"
  value       = module.gke.cluster_name
}

output "cluster_endpoint" {
  description = "The endpoint of the GKE cluster"
  value       = module.gke.cluster_endpoint
}

output "mlflow_artifacts_bucket" {
  description = "The name of the GCS bucket for MLflow artifacts"
  value       = google_storage_bucket.mlflow_artifacts.name
}

output "mlflow_backups_bucket" {
  description = "The name of the GCS bucket for MLflow backups"
  value       = google_storage_bucket.mlflow_backups.name
}

output "mlflow_service_account" {
  description = "The email of the MLflow service account"
  value       = google_service_account.mlflow.email
}

output "developer_platform_namespace" {
  description = "The Kubernetes namespace for the developer platform"
  value       = kubernetes_namespace.developer_platform.metadata[0].name
} 