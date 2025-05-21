variable "argocd_hostname" {
  description = "The hostname for ArgoCD ingress"
  type        = string
}

variable "admin_password_hash" {
  description = "Bcrypt hash of the admin password"
  type        = string
  sensitive   = true
} 