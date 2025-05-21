#!/bin/bash
set -euo pipefail

# Default values
PROJECT_ID=""
REGION="us-central1"
DOMAIN=""
ARGOCD_PASSWORD=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --project-id)
      PROJECT_ID="$2"
      shift 2
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    --domain)
      DOMAIN="$2"
      shift 2
      ;;
    --argocd-password)
      ARGOCD_PASSWORD="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Validate required arguments
if [[ -z "$PROJECT_ID" ]] || [[ -z "$DOMAIN" ]] || [[ -z "$ARGOCD_PASSWORD" ]]; then
  echo "Error: Missing required arguments"
  echo "Usage: $0 --project-id=<project-id> --domain=<domain> --argocd-password=<password> [--region=<region>]"
  exit 1
fi

echo "🚀 Starting bootstrap process..."

# Enable required GCP APIs
echo "📡 Enabling required GCP APIs..."
gcloud services enable \
  container.googleapis.com \
  artifactregistry.googleapis.com \
  iam.googleapis.com \
  cloudresourcemanager.googleapis.com

# Create GCS bucket for Terraform state
BUCKET_NAME="${PROJECT_ID}-tfstate"
echo "📦 Creating GCS bucket for Terraform state: ${BUCKET_NAME}"
gsutil mb -p "$PROJECT_ID" -l "$REGION" "gs://${BUCKET_NAME}" || true
gsutil versioning set on "gs://${BUCKET_NAME}"

# Create service account for GKE nodes
SA_NAME="gke-node-sa"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
echo "🔑 Creating service account for GKE nodes: ${SA_NAME}"
gcloud iam service-accounts create "$SA_NAME" \
  --display-name="GKE Node Service Account" || true

# Grant required roles
echo "🔐 Granting required roles to service account..."
for role in \
  roles/artifactregistry.reader \
  roles/storage.objectViewer \
  roles/monitoring.metricWriter \
  roles/monitoring.viewer \
  roles/logging.logWriter; do
  gcloud projects add-iam-policy-binding "$PROJECT_ID" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="$role"
done

# Generate bcrypt hash for ArgoCD admin password
echo "🔒 Generating bcrypt hash for ArgoCD password..."
ARGOCD_PASSWORD_HASH=$(htpasswd -bnBC 10 "" "$ARGOCD_PASSWORD" | tr -d ':\n' | sed 's/$2y/$2a/')

# Create terraform.tfvars
echo "📝 Creating terraform.tfvars..."
cat > infra/environments/prod/terraform.tfvars <<EOF
project_id = "${PROJECT_ID}"
region = "${REGION}"
node_service_account = "${SA_EMAIL}"
domain = "${DOMAIN}"
argocd_admin_password_hash = "${ARGOCD_PASSWORD_HASH}"
EOF

# Initialize and apply Terraform
echo "🏗️ Initializing Terraform..."
cd infra/environments/prod
terraform init

echo "🚀 Applying Terraform configuration..."
terraform apply -auto-approve

echo "✅ Bootstrap complete!"
echo "ArgoCD will be available at: https://argocd.${DOMAIN}"
echo "JupyterHub will be available at: https://jupyter.${DOMAIN}"
echo "Grafana will be available at: https://grafana.${DOMAIN}" 