terraform {
  required_version = ">= 1.0.0"
  
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
  }

  backend "gcs" {
    bucket = "tf-state-developer-platform"
    prefix = "dev"
  }
}

# Additional variables for security features
variable "billing_account_id" {
  description = "The ID of the billing account to associate with the budget"
  type        = string
}

variable "monthly_budget_amount" {
  description = "Monthly budget amount in USD"
  type        = number
  default     = 1000
}

variable "cost_center" {
  description = "Cost center for resource tagging"
  type        = string
}

variable "business_unit" {
  description = "Business unit for resource tagging"
  type        = string
}

variable "security_team_email" {
  description = "Email address for security notifications"
  type        = string
}

# Define common labels/tags
locals {
  common_labels = {
    environment     = var.environment
    cost_center    = var.cost_center
    business_unit  = var.business_unit
    managed_by     = "terraform"
    created_by     = "developer-platform"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "kubernetes" {
  host                   = module.gke.cluster_endpoint
  cluster_ca_certificate = base64decode(module.gke.cluster_ca_certificate)
  token                  = data.google_client_config.current.access_token
}

# Get current client config
data "google_client_config" "current" {}

# VPC Module
module "vpc" {
  source = "../../modules/vpc"
  
  project_id = var.project_id
  region     = var.region
  env        = var.environment
}

# GKE Module
module "gke" {
  source = "../../modules/gke"
  
  project_id    = var.project_id
  region        = var.region
  env           = var.environment
  cluster_name  = var.cluster_name
  network_name  = module.vpc.network_name
  subnet_name   = module.vpc.subnet_name
}

# Create GCS buckets for MLflow
resource "google_storage_bucket" "mlflow_artifacts" {
  name          = "${var.mlflow_config.artifact_bucket}-${var.project_id}"
  location      = var.region
  encryption {
    default_kms_key_name = google_kms_crypto_key.storage.id
  }
  force_destroy = var.environment == "dev" ? true : false

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  security {
    tls_enabled = true
  }

  labels = merge(local.common_labels, {
    purpose = "mlflow-artifacts"
  })

  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_storage_bucket" "mlflow_backups" {
  name          = "${var.mlflow_config.backup_bucket}-${var.project_id}"
  location      = var.region
  encryption {
    default_kms_key_name = google_kms_crypto_key.storage.id
  }
  force_destroy = var.environment == "dev" ? true : false

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  security {
    tls_enabled = true
  }

  labels = merge(local.common_labels, {
    purpose = "mlflow-backups"
  })

  lifecycle_rule {
    condition {
      age = var.mlflow_config.retention_days
    }
    action {
      type = "Delete"
    }
  }
}

# Enable required APIs
resource "google_project_service" "sqladmin" {
  service = "sqladmin.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "iam" {
  service = "iam.googleapis.com"
  disable_on_destroy = false
}

# Enable monitoring APIs
resource "google_project_service" "monitoring" {
  service = "monitoring.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "logging" {
  service = "logging.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "kms" {
  service = "cloudkms.googleapis.com"
  disable_on_destroy = false
}

# Enable Container Analysis API for security scanning
resource "google_project_service" "container_scanning" {
  service = "containeranalysis.googleapis.com"
  disable_on_destroy = false
}

# Configure vulnerability scanning
resource "google_container_analysis_note" "vulnz_scanning" {
  name = "vulnerability-scanning"
  project = var.project_id

  vulnerability_note {
    severity = "CRITICAL"
    details {
      affected_cpe_uri = "cpe:/o:debian:debian_linux:10"
      affected_package = "all"
      fixed_version {
        kind = "MAXIMUM"
      }
    }
  }
}

# Enable Binary Authorization
resource "google_binary_authorization_policy" "policy" {
  project = var.project_id

  default_admission_rule {
    evaluation_mode  = "ALWAYS_ALLOW"
    enforcement_mode = "ENFORCED_BLOCK_AND_AUDIT_LOG"
  }

  admission_whitelist_patterns {
    name_pattern = "gcr.io/${var.project_id}/*"
  }
}

# Create Cloud SQL instance
resource "google_sql_database_instance" "mlflow" {
  name             = "mlflow-${var.environment}"
  database_version = "POSTGRES_${var.mlflow_config.db_version}"
  region           = var.region
  
  depends_on = [google_project_service.sqladmin]

  encryption_key_name = google_kms_crypto_key.sql.id

  settings {
    tier = "db-custom-${var.mlflow_resources.database.cpu_request}-${regex("\\d+", var.mlflow_resources.database.memory_request)}"
    
    backup_configuration {
      enabled    = true
      start_time = "01:00"
      location   = var.region
      
      backup_retention_settings {
        retained_backups = var.mlflow_config.retention_days
        retention_unit   = "COUNT"
      }
    }

    ip_configuration {
      ipv4_enabled = false
      private_network = module.vpc.network_id
      require_ssl = true
    }

    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }

    database_flags {
      name  = "ssl_require"
      value = "on"
    }

    user_labels = local.common_labels
  }

  deletion_protection = var.environment == "prod" ? true : false
}

# Create MLflow database
resource "google_sql_database" "mlflow" {
  name     = "mlflow"
  instance = google_sql_database_instance.mlflow.name
}

# Create service account for MLflow
resource "google_service_account" "mlflow" {
  account_id   = "mlflow-sa"
  display_name = "MLflow Service Account"
}

# Grant Cloud SQL access to service account
resource "google_project_iam_member" "mlflow_cloudsql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.mlflow.email}"
}

# Grant storage permissions
resource "google_project_iam_member" "mlflow_storage" {
  project = var.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.mlflow.email}"
}

# Enable Workload Identity
resource "google_service_account_iam_binding" "workload_identity" {
  service_account_id = google_service_account.mlflow.name
  role               = "roles/iam.workloadIdentityUser"
  members = [
    "serviceAccount:${var.project_id}.svc.id.goog[${kubernetes_namespace.developer_platform.metadata[0].name}/mlflow]"
  ]
}

# Create Kubernetes service account for MLflow
resource "kubernetes_service_account" "mlflow" {
  metadata {
    name      = "mlflow"
    namespace = kubernetes_namespace.developer_platform.metadata[0].name
    annotations = {
      "iam.gke.io/gcp-service-account" = google_service_account.mlflow.email
    }
  }
}

# Create Cloud SQL IAM user for MLflow
resource "google_sql_user" "mlflow" {
  name     = google_service_account.mlflow.email
  instance = google_sql_database_instance.mlflow.name
  type     = "CLOUD_IAM_SERVICE_ACCOUNT"
}

# Create Kubernetes namespace
resource "kubernetes_namespace" "developer_platform" {
  metadata {
    name = "developer-platform"
  }
}

# Create persistent volume claim for PostgreSQL
resource "kubernetes_persistent_volume_claim" "mlflow_db" {
  metadata {
    name      = "mlflow-db-pvc"
    namespace = kubernetes_namespace.developer_platform.metadata[0].name
  }

  spec {
    access_modes = ["ReadWriteOnce"]
    resources {
      requests = {
        storage = var.mlflow_config.db_storage_size
      }
    }
  }
}

# Create PostgreSQL StatefulSet
resource "kubernetes_stateful_set" "mlflow_db" {
  metadata {
    name      = "mlflow-db"
    namespace = kubernetes_namespace.developer_platform.metadata[0].name
    labels = {
      app = "mlflow-db"
    }
  }

  spec {
    service_name = "mlflow-db"
    replicas     = 1

    selector {
      match_labels = {
        app = "mlflow-db"
      }
    }

    template {
      metadata {
        labels = {
          app = "mlflow-db"
        }
      }

      spec {
        container {
          name  = "postgres"
          image = "postgres:${var.mlflow_config.db_version}"

          env {
            name = "POSTGRES_USER"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.mlflow_db_credentials.metadata[0].name
                key  = "username"
              }
            }
          }

          env {
            name = "POSTGRES_PASSWORD"
            value_from {
              secret_key_ref {
                name = kubernetes_secret.mlflow_db_credentials.metadata[0].name
                key  = "password"
              }
            }
          }

          env {
            name  = "POSTGRES_DB"
            value = "mlflow"
          }

          port {
            container_port = 5432
          }

          resources {
            requests = {
              cpu    = var.mlflow_resources.database.cpu_request
              memory = var.mlflow_resources.database.memory_request
            }
            limits = {
              cpu    = var.mlflow_resources.database.cpu_limit
              memory = var.mlflow_resources.database.memory_limit
            }
          }

          volume_mount {
            name       = "mlflow-db-storage"
            mount_path = "/var/lib/postgresql/data"
          }

          liveness_probe {
            exec {
              command = ["pg_isready", "-U", "mlflow"]
            }
            initial_delay_seconds = 30
            period_seconds       = 10
          }

          readiness_probe {
            exec {
              command = ["pg_isready", "-U", "mlflow"]
            }
            initial_delay_seconds = 5
            period_seconds       = 5
          }
        }

        volume {
          name = "mlflow-db-storage"
          persistent_volume_claim {
            claim_name = kubernetes_persistent_volume_claim.mlflow_db.metadata[0].name
          }
        }
      }
    }
  }
}

# Create PostgreSQL Service
resource "kubernetes_service" "mlflow_db" {
  metadata {
    name      = "mlflow-db"
    namespace = kubernetes_namespace.developer_platform.metadata[0].name
  }

  spec {
    selector = {
      app = "mlflow-db"
    }

    port {
      port        = 5432
      target_port = 5432
    }

    type = "ClusterIP"
  }
}

# Create Kubernetes secrets
resource "kubernetes_secret" "mlflow_gcp_credentials" {
  metadata {
    name      = "mlflow-gcp-credentials"
    namespace = kubernetes_namespace.developer_platform.metadata[0].name
  }

  data = {
    "credentials.json" = base64decode(google_service_account_key.mlflow.private_key)
  }
}

resource "kubernetes_secret" "mlflow_db_credentials" {
  metadata {
    name      = "mlflow-db-credentials"
    namespace = kubernetes_namespace.developer_platform.metadata[0].name
  }

  data = {
    username = "mlflow"
    password = random_password.db_password.result
  }
}

# Generate random password for database
resource "random_password" "db_password" {
  length  = 32
  special = true
}

# Create service account key
resource "google_service_account_key" "mlflow" {
  service_account_id = google_service_account.mlflow.name
}

# Create MLflow deployment with Cloud SQL Auth Proxy
resource "kubernetes_deployment" "mlflow" {
  metadata {
    name      = "mlflow"
    namespace = kubernetes_namespace.developer_platform.metadata[0].name
  }

  spec {
    replicas = 1

    selector {
      match_labels = {
        app = "mlflow"
      }
    }

    template {
      metadata {
        labels = {
          app = "mlflow"
        }
      }

      spec {
        service_account_name = kubernetes_service_account.mlflow.metadata[0].name

        container {
          name  = "cloud-sql-proxy"
          image = "gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.1.0"
          args  = [
            "--structured-logs",
            "--port=5432",
            "${var.project_id}:${var.region}:${google_sql_database_instance.mlflow.name}"
          ]

          resources {
            requests = {
              cpu    = "100m"
              memory = "100Mi"
            }
            limits = {
              cpu    = "200m"
              memory = "200Mi"
            }
          }

          security_context {
            run_as_non_root = true
          }
        }

        container {
          name  = "mlflow"
          image = "ghcr.io/mlflow/mlflow:${var.mlflow_config.version}"

          env {
            name  = "MLFLOW_TRACKING_URI"
            value = "postgresql+psycopg2://${google_service_account.mlflow.email}@/${google_sql_database.mlflow.name}?host=/cloudsql/${var.project_id}:${var.region}:${google_sql_database_instance.mlflow.name}"
          }

          env {
            name  = "MLFLOW_DEFAULT_ARTIFACT_ROOT"
            value = "gs://${google_storage_bucket.mlflow_artifacts.name}"
          }

          env {
            name  = "MLFLOW_TRACKING_INSECURE_TLS"
            value = "false"
          }

          env {
            name  = "MLFLOW_TRACKING_SERVER_CERT_PATH"
            value = "/etc/mlflow/tls/tls.crt"
          }

          env {
            name  = "MLFLOW_TRACKING_SERVER_KEY_PATH"
            value = "/etc/mlflow/tls/tls.key"
          }

          resources {
            requests = {
              cpu    = var.mlflow_resources.server.cpu_request
              memory = var.mlflow_resources.server.memory_request
            }
            limits = {
              cpu    = var.mlflow_resources.server.cpu_limit
              memory = var.mlflow_resources.server.memory_limit
            }
          }

          volume_mount {
            name       = "tls"
            mount_path = "/etc/mlflow/tls"
            read_only  = true
          }
        }
      }
    }
  }
}

# Create MLflow service
resource "kubernetes_service" "mlflow" {
  metadata {
    name      = "mlflow"
    namespace = kubernetes_namespace.developer_platform.metadata[0].name
  }

  spec {
    selector = {
      app = "mlflow"
    }

    port {
      port        = 5000
      target_port = 5000
    }

    type = "ClusterIP"
  }
}

# Create monitoring notification channel (optional)
resource "google_monitoring_notification_channel" "email" {
  display_name = "MLflow Database Alerts"
  type         = "email"
  
  labels = {
    email_address = var.alert_email
  }

  depends_on = [google_project_service.monitoring]
}

# Create security notification channel
resource "google_monitoring_notification_channel" "security_email" {
  display_name = "Security Event Notifications"
  type         = "email"
  
  labels = {
    email_address = var.security_team_email
  }

  depends_on = [google_project_service.monitoring]
}

# Create budget alert
resource "google_billing_budget" "project_budget" {
  billing_account = var.billing_account_id
  display_name    = "${var.environment}-environment-budget"

  budget_filter {
    projects = ["projects/${var.project_id}"]
    labels = {
      environment = var.environment
    }
  }

  amount {
    specified_amount {
      currency_code = "USD"
      units        = var.monthly_budget_amount
    }
  }

  threshold_rules {
    threshold_percent = 0.5  # Alert at 50%
    spend_basis      = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 0.8  # Alert at 80%
    spend_basis      = "CURRENT_SPEND"
  }

  threshold_rules {
    threshold_percent = 0.9  # Alert at 90%
    spend_basis      = "CURRENT_SPEND"
  }

  all_updates_rule {
    monitoring_notification_channels = [
      google_monitoring_notification_channel.email.name,
      google_monitoring_notification_channel.security_email.name
    ]
    disable_default_iam_recipients = true
  }
}

# Create monitoring alert policies
resource "google_monitoring_alert_policy" "cpu_usage" {
  display_name = "MLflow Database CPU Usage"
  combiner     = "OR"
  
  conditions {
    display_name = "CPU Utilization"
    
    condition_threshold {
      filter          = "resource.type = \"cloudsql_database\" AND resource.labels.database_id = \"${google_sql_database_instance.mlflow.name}\" AND metric.type = \"cloudsql.googleapis.com/database/cpu/utilization\""
      duration        = "300s"
      comparison     = "COMPARISON_GT"
      threshold_value = 0.8  # 80% CPU utilization
      
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.name]
  depends_on = [google_project_service.monitoring]
}

resource "google_monitoring_alert_policy" "memory_usage" {
  display_name = "MLflow Database Memory Usage"
  combiner     = "OR"
  
  conditions {
    display_name = "Memory Utilization"
    
    condition_threshold {
      filter          = "resource.type = \"cloudsql_database\" AND resource.labels.database_id = \"${google_sql_database_instance.mlflow.name}\" AND metric.type = \"cloudsql.googleapis.com/database/memory/utilization\""
      duration        = "300s"
      comparison     = "COMPARISON_GT"
      threshold_value = 0.85  # 85% memory utilization
      
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.name]
  depends_on = [google_project_service.monitoring]
}

resource "google_monitoring_alert_policy" "disk_usage" {
  display_name = "MLflow Database Disk Usage"
  combiner     = "OR"
  
  conditions {
    display_name = "Disk Utilization"
    
    condition_threshold {
      filter          = "resource.type = \"cloudsql_database\" AND resource.labels.database_id = \"${google_sql_database_instance.mlflow.name}\" AND metric.type = \"cloudsql.googleapis.com/database/disk/utilization\""
      duration        = "300s"
      comparison     = "COMPARISON_GT"
      threshold_value = 0.85  # 85% disk utilization
      
      aggregations {
        alignment_period   = "60s"
        per_series_aligner = "ALIGN_MEAN"
      }
    }
  }

  notification_channels = [google_monitoring_notification_channel.email.name]
  depends_on = [google_project_service.monitoring]
}

# Create Cloud SQL dashboard
resource "google_monitoring_dashboard" "mlflow" {
  dashboard_json = jsonencode({
    displayName = "MLflow Database Monitoring"
    gridLayout = {
      columns = "2"
      widgets = [
        {
          title = "CPU Utilization"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type = \"cloudsql_database\" AND resource.labels.database_id = \"${google_sql_database_instance.mlflow.name}\" AND metric.type = \"cloudsql.googleapis.com/database/cpu/utilization\""
                }
              }
            }]
          }
        },
        {
          title = "Memory Utilization"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type = \"cloudsql_database\" AND resource.labels.database_id = \"${google_sql_database_instance.mlflow.name}\" AND metric.type = \"cloudsql.googleapis.com/database/memory/utilization\""
                }
              }
            }]
          }
        },
        {
          title = "Disk Utilization"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type = \"cloudsql_database\" AND resource.labels.database_id = \"${google_sql_database_instance.mlflow.name}\" AND metric.type = \"cloudsql.googleapis.com/database/disk/utilization\""
                }
              }
            }]
          }
        },
        {
          title = "Active Connections"
          xyChart = {
            dataSets = [{
              timeSeriesQuery = {
                timeSeriesFilter = {
                  filter = "resource.type = \"cloudsql_database\" AND resource.labels.database_id = \"${google_sql_database_instance.mlflow.name}\" AND metric.type = \"cloudsql.googleapis.com/database/postgresql/num_backends\""
                }
              }
            }]
          }
        }
      ]
    }
  })
  depends_on = [google_project_service.monitoring]
}

# Add logging sink for database logs
resource "google_logging_project_sink" "mlflow_db" {
  name        = "mlflow-db-logs"
  destination = "storage.googleapis.com/${google_storage_bucket.mlflow_backups.name}/logs"
  filter      = "resource.type=cloudsql_database AND resource.labels.database_id=${google_sql_database_instance.mlflow.name}"

  unique_writer_identity = true
  depends_on = [google_project_service.logging]
}

# Create enhanced audit logging sink
resource "google_logging_project_sink" "enhanced_audit" {
  name        = "enhanced-audit-logs"
  project     = var.project_id
  destination = "storage.googleapis.com/${google_storage_bucket.mlflow_backups.name}/enhanced-audit"
  
  filter      = <<EOT
    resource.type=("gce_instance" OR "cloud_function" OR "cloud_run_revision" OR "k8s_container")
    OR
    protoPayload.methodName=("SetIamPolicy" OR "google.iam.v1.IAMPolicy.SetIamPolicy")
    OR
    severity >= WARNING
    OR
    resource.type="k8s_cluster"
    OR
    resource.type="cloudsql_database"
  EOT

  unique_writer_identity = true
  depends_on = [google_project_service.logging]
}

# Create security event alert policy
resource "google_monitoring_alert_policy" "security_events" {
  display_name = "Security Events Alert"
  combiner     = "OR"
  
  conditions {
    display_name = "Critical Security Events"
    condition_threshold {
      filter     = "resource.type = \"audited_resource\" AND severity >= ERROR"
      duration   = "0s"
      comparison = "COMPARISON_GT"
      threshold_value = 0
      trigger {
        count = 1
      }
    }
  }

  conditions {
    display_name = "IAM Changes"
    condition_threshold {
      filter     = "protoPayload.methodName = \"SetIamPolicy\" OR protoPayload.methodName = \"google.iam.v1.IAMPolicy.SetIamPolicy\""
      duration   = "0s"
      comparison = "COMPARISON_GT"
      threshold_value = 0
      trigger {
        count = 1
      }
    }
  }

  conditions {
    display_name = "GKE Security Events"
    condition_threshold {
      filter     = "resource.type = \"k8s_cluster\" AND severity >= WARNING"
      duration   = "0s"
      comparison = "COMPARISON_GT"
      threshold_value = 0
      trigger {
        count = 1
      }
    }
  }

  notification_channels = [
    google_monitoring_notification_channel.security_email.name
  ]

  documentation {
    content = "Security event detected. Please investigate immediately."
    mime_type = "text/markdown"
  }

  depends_on = [google_project_service.monitoring]
}

# Add retention policy for audit logs
resource "google_storage_bucket_lifecycle_rule" "audit_logs_retention" {
  bucket = google_storage_bucket.mlflow_backups.name
  
  action {
    type = "Delete"
  }
  
  condition {
    age = 365  # 1 year retention
    with_state = "ANY"
    matches_prefix = ["enhanced-audit/"]
  }
}

# Grant log writer access to the sink
resource "google_project_iam_binding" "log_writer" {
  project = var.project_id
  role    = "roles/storage.objectCreator"
  members = [google_logging_project_sink.mlflow_db.writer_identity]
}

# Create KMS keyring
resource "google_kms_key_ring" "mlflow" {
  name     = "mlflow-keyring"
  location = var.region
  depends_on = [google_project_service.kms]
}

# Create KMS key for Cloud SQL
resource "google_kms_crypto_key" "sql" {
  name            = "mlflow-sql-key"
  key_ring        = google_kms_key_ring.mlflow.id
  rotation_period = "7776000s" # 90 days

  version_template {
    algorithm        = "GOOGLE_SYMMETRIC_ENCRYPTION"
    protection_level = "SOFTWARE"
  }

  lifecycle {
    prevent_destroy = true
  }
}

# Create KMS key for GCS
resource "google_kms_crypto_key" "storage" {
  name            = "mlflow-storage-key"
  key_ring        = google_kms_key_ring.mlflow.id
  rotation_period = "7776000s" # 90 days

  version_template {
    algorithm        = "GOOGLE_SYMMETRIC_ENCRYPTION"
    protection_level = "SOFTWARE"
  }

  lifecycle {
    prevent_destroy = true
  }
}

# Grant Cloud SQL service account access to KMS
resource "google_kms_crypto_key_iam_member" "sql" {
  crypto_key_id = google_kms_crypto_key.sql.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${google_sql_database_instance.mlflow.service_account_email_address}"
}

# Grant Storage service account access to KMS
data "google_storage_project_service_account" "gcs_account" {
}

resource "google_kms_crypto_key_iam_member" "storage" {
  crypto_key_id = google_kms_crypto_key.storage.id
  role          = "roles/cloudkms.cryptoKeyEncrypterDecrypter"
  member        = "serviceAccount:${data.google_storage_project_service_account.gcs_account.email_address}"
}

# Create TLS certificate for MLflow
resource "google_certificate_manager_certificate" "mlflow" {
  name        = "mlflow-cert"
  description = "MLflow TLS certificate"
  scope       = "DEFAULT"
  managed {
    domains = ["mlflow.${var.domain}"]
  }
}

# Create Kubernetes TLS secret
resource "kubernetes_secret" "mlflow_tls" {
  metadata {
    name      = "mlflow-tls"
    namespace = kubernetes_namespace.developer_platform.metadata[0].name
  }

  data = {
    "tls.crt" = google_certificate_manager_certificate.mlflow.certificate_pem
    "tls.key" = google_certificate_manager_certificate.mlflow.private_key_pem
  }

  type = "kubernetes.io/tls"
} 