#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Function to prompt for confirmation
confirm() {
    read -r -p "${1:-Are you sure? [y/N]} " response
    case "$response" in
        [yY][eE][sS]|[yY]) 
            true
            ;;
        *)
            false
            ;;
    esac
}

# Get project configuration
PROJECT_ID=$(gcloud config get-value project)
REGION=$(gcloud config get-value compute/region)
echo -e "${YELLOW}Current Project: ${PROJECT_ID}${NC}"
echo -e "${YELLOW}Current Region: ${REGION}${NC}"

if ! confirm "This will delete all MLflow resources. Are you sure you want to continue? [y/N]"; then
    echo -e "${RED}Cleanup cancelled${NC}"
    exit 1
fi

echo -e "\n${YELLOW}Starting MLflow cleanup...${NC}"

# Function to run command with error handling
run_cmd() {
    if eval "$1"; then
        echo -e "${GREEN}✓ $2${NC}"
    else
        echo -e "${RED}✗ $2${NC}"
        if ! confirm "Continue anyway? [y/N]"; then
            echo -e "${RED}Cleanup aborted${NC}"
            exit 1
        fi
    fi
}

# 1. Remove monitoring resources
echo -e "\n${YELLOW}Removing monitoring resources...${NC}"
run_cmd "gcloud monitoring policies delete \$(gcloud monitoring policies list --filter='displayName:MLflow Database CPU Usage' --format='value(name)') --quiet 2>/dev/null || true" "Removed CPU monitoring policy"
run_cmd "gcloud monitoring policies delete \$(gcloud monitoring policies list --filter='displayName:MLflow Database Memory Usage' --format='value(name)') --quiet 2>/dev/null || true" "Removed memory monitoring policy"
run_cmd "gcloud monitoring policies delete \$(gcloud monitoring policies list --filter='displayName:MLflow Database Disk Usage' --format='value(name)') --quiet 2>/dev/null || true" "Removed disk monitoring policy"

# 2. Remove logging sink
echo -e "\n${YELLOW}Removing logging configuration...${NC}"
run_cmd "gcloud logging sinks delete mlflow-db-logs --quiet 2>/dev/null || true" "Removed logging sink"

# 3. Export data before deletion (optional)
if confirm "Would you like to export MLflow data before deletion? [y/N]"; then
    TIMESTAMP=$(date +%Y%m%d-%H%M%S)
    EXPORT_DIR="mlflow-export-${TIMESTAMP}"
    mkdir -p "${EXPORT_DIR}"
    
    echo -e "\n${YELLOW}Exporting MLflow data...${NC}"
    
    # Export database
    echo -e "${YELLOW}Exporting Cloud SQL database...${NC}"
    run_cmd "gcloud sql export sql mlflow-dev gs://${PROJECT_ID}-mlflow-backups/final-backup-${TIMESTAMP}.sql --database=mlflow 2>/dev/null || true" "Exported database"
    
    # Export artifacts
    echo -e "${YELLOW}Exporting artifacts...${NC}"
    run_cmd "gsutil -m cp -r gs://${PROJECT_ID}-mlflow-artifacts/* ${EXPORT_DIR}/artifacts/ 2>/dev/null || true" "Exported artifacts"
    
    echo -e "${GREEN}Data exported to ${EXPORT_DIR}${NC}"
fi

# 4. Remove Kubernetes resources
echo -e "\n${YELLOW}Removing Kubernetes resources...${NC}"
run_cmd "kubectl delete deployment mlflow -n developer-platform --ignore-not-found" "Removed MLflow deployment"
run_cmd "kubectl delete service mlflow -n developer-platform --ignore-not-found" "Removed MLflow service"
run_cmd "kubectl delete secret mlflow-gcp-credentials -n developer-platform --ignore-not-found" "Removed MLflow secrets"
run_cmd "kubectl delete serviceaccount mlflow -n developer-platform --ignore-not-found" "Removed MLflow service account"

# 5. Remove Cloud SQL instance
echo -e "\n${YELLOW}Removing Cloud SQL instance...${NC}"
if confirm "This will delete the Cloud SQL instance and all its data. Continue? [y/N]"; then
    run_cmd "gcloud sql instances delete mlflow-dev --quiet" "Removed Cloud SQL instance"
fi

# 6. Remove GCS buckets
echo -e "\n${YELLOW}Removing GCS buckets...${NC}"
if confirm "This will delete all MLflow artifacts and backups. Continue? [y/N]"; then
    run_cmd "gsutil -m rm -r gs://${PROJECT_ID}-mlflow-artifacts/** 2>/dev/null || true" "Cleared artifacts bucket"
    run_cmd "gsutil -m rm -r gs://${PROJECT_ID}-mlflow-backups/** 2>/dev/null || true" "Cleared backups bucket"
    run_cmd "gsutil rb gs://${PROJECT_ID}-mlflow-artifacts 2>/dev/null || true" "Removed artifacts bucket"
    run_cmd "gsutil rb gs://${PROJECT_ID}-mlflow-backups 2>/dev/null || true" "Removed backups bucket"
fi

# 7. Remove IAM resources
echo -e "\n${YELLOW}Removing IAM resources...${NC}"
SA_EMAIL="mlflow-sa@${PROJECT_ID}.iam.gserviceaccount.com"
run_cmd "gcloud iam service-accounts delete ${SA_EMAIL} --quiet 2>/dev/null || true" "Removed service account"

# 8. Remove monitoring dashboard
echo -e "\n${YELLOW}Removing monitoring dashboard...${NC}"
run_cmd "gcloud monitoring dashboards delete \$(gcloud monitoring dashboards list --filter='displayName:MLflow Database Monitoring' --format='value(name)') --quiet 2>/dev/null || true" "Removed dashboard"

# Final Terraform cleanup
echo -e "\n${YELLOW}Running Terraform destroy...${NC}"
if confirm "Would you like to run 'terraform destroy' to clean up remaining resources? [y/N]"; then
    cd infra/environments/dev
    terraform destroy -auto-approve
fi

echo -e "\n${GREEN}MLflow cleanup completed!${NC}"
echo -e "\n${YELLOW}Manual Verification Steps:${NC}"
echo "1. Verify in Cloud Console that all resources are removed"
echo "2. Check Cloud SQL instances"
echo "3. Check GCS buckets"
echo "4. Check IAM service accounts"
echo "5. Check Kubernetes resources"
echo "6. Check monitoring and logging configurations"

if [[ -d "${EXPORT_DIR}" ]]; then
    echo -e "\n${YELLOW}Backup Information:${NC}"
    echo "Your MLflow data has been exported to: ${EXPORT_DIR}"
    echo "Make sure to save this directory if you need the data later"
fi 