variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "region" {
  description = "The region to host the cluster in"
  type        = string
  default     = "us-central1"
}

variable "node_service_account" {
  description = "The service account to use for GKE nodes"
  type        = string
}

variable "domain" {
  description = "The base domain for ingress resources"
  type        = string
}

variable "argocd_admin_password_hash" {
  description = "Bcrypt hash of the ArgoCD admin password"
  type        = string
  sensitive   = true
} 