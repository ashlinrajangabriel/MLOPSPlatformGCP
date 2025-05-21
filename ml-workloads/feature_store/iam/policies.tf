resource "google_service_account" "feature_server" {
  account_id   = "feature-server"
  display_name = "Feature Server Service Account"
  project      = var.project_id
}

# GCS permissions
resource "google_storage_bucket_iam_member" "feature_server_gcs" {
  bucket = var.gcs_bucket_name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.feature_server.email}"
}

# Datastore permissions
resource "google_project_iam_member" "feature_server_datastore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.feature_server.email}"
}

# KMS permissions for encryption
resource "google_kms_crypto_key_iam_member" "feature_server_kms" {
  crypto_key_id = var.kms_key_id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${google_service_account.feature_server.email}"
}

# Workload Identity binding
resource "google_service_account_iam_binding" "workload_identity" {
  service_account_id = google_service_account.feature_server.name
  role               = "roles/iam.workloadIdentityUser"
  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[default/feature-server-sa]"
  ]
}

# Variables
variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "gcs_bucket_name" {
  description = "GCS Bucket Name"
  type        = string
}

variable "kms_key_id" {
  description = "KMS Key ID for encryption"
  type        = string
}

# Airflow service account
resource "google_service_account" "airflow" {
  account_id   = "airflow-worker"
  display_name = "Airflow Worker Service Account"
  project      = var.project_id
}

# Airflow GCS permissions
resource "google_storage_bucket_iam_member" "airflow_gcs" {
  bucket = var.gcs_bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.airflow.email}"
}

# Airflow Datastore permissions
resource "google_project_iam_member" "airflow_datastore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.airflow.email}"
}

# Airflow KMS permissions
resource "google_kms_crypto_key_iam_member" "airflow_kms" {
  crypto_key_id = var.kms_key_id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${google_service_account.airflow.email}"
}

# MLflow service account
resource "google_service_account" "mlflow" {
  account_id   = "mlflow-tracking"
  display_name = "MLflow Tracking Service Account"
  project      = var.project_id
}

# MLflow GCS permissions for artifact storage
resource "google_storage_bucket_iam_member" "mlflow_gcs" {
  bucket = var.gcs_bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.mlflow.email}"
} 