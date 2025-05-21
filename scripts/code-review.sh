#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "Running Production Code Review Checks..."

# 1. Security Checks
echo -e "\n${YELLOW}1. Security Checks${NC}"

# Check for hardcoded secrets
echo -e "\nChecking for potential hardcoded secrets..."
find . -type f -not -path "*/\.*" -exec grep -l -i "password\|secret\|key\|token" {} \;

# Check for proper RBAC configuration
echo -e "\nVerifying RBAC configurations..."
kubectl get clusterroles,clusterrolebindings,roles,rolebindings -A

# Check TLS/certificate configuration
echo -e "\nChecking TLS configurations..."
kubectl get certificates,certificaterequests,orders,challenges -A

# 2. Resource Management
echo -e "\n${YELLOW}2. Resource Management${NC}"

# Check resource requests/limits
echo -e "\nChecking resource configurations..."
kubectl get pods -A -o custom-columns='NAMESPACE:.metadata.namespace,NAME:.metadata.name,REQUESTS_CPU:.spec.containers[*].resources.requests.cpu,REQUESTS_MEM:.spec.containers[*].resources.requests.memory,LIMITS_CPU:.spec.containers[*].resources.limits.cpu,LIMITS_MEM:.spec.containers[*].resources.limits.memory'

# Check HPA configuration
echo -e "\nVerifying HPA settings..."
kubectl get hpa -A

# 3. Monitoring & Observability
echo -e "\n${YELLOW}3. Monitoring & Observability${NC}"

# Check Prometheus configuration
echo -e "\nChecking monitoring setup..."
kubectl get servicemonitors,prometheusrules -A

# Check logging configuration
echo -e "\nVerifying logging setup..."
kubectl get pods -l app=fluentd -A

# 4. High Availability
echo -e "\n${YELLOW}4. High Availability${NC}"

# Check pod distribution
echo -e "\nChecking pod distribution..."
kubectl get pods -o wide -A

# Check PDB configuration
echo -e "\nVerifying PodDisruptionBudgets..."
kubectl get pdb -A

# 5. Code Quality
echo -e "\n${YELLOW}5. Code Quality${NC}"

# Check API versions
echo -e "\nChecking API versions..."
kubectl api-resources --verbs=list -o wide

# Check label consistency
echo -e "\nVerifying label consistency..."
kubectl get all -A -o json | jq '.items[].metadata.labels'

# 6. Compliance
echo -e "\n${YELLOW}6. Compliance${NC}"

# Check network policies
echo -e "\nChecking network policies..."
kubectl get networkpolicies -A

# Check pod security policies
echo -e "\nVerifying pod security policies..."
kubectl get psp

# Summary
echo -e "\n${YELLOW}Summary of Findings:${NC}"
echo "----------------------------------------"

# Count resources
PODS=$(kubectl get pods -A | wc -l)
SERVICES=$(kubectl get svc -A | wc -l)
INGRESS=$(kubectl get ingress -A | wc -l)
SECRETS=$(kubectl get secrets -A | wc -l)
CONFIGMAPS=$(kubectl get configmaps -A | wc -l)

echo -e "Total Pods: ${GREEN}$PODS${NC}"
echo -e "Total Services: ${GREEN}$SERVICES${NC}"
echo -e "Total Ingress: ${GREEN}$INGRESS${NC}"
echo -e "Total Secrets: ${GREEN}$SECRETS${NC}"
echo -e "Total ConfigMaps: ${GREEN}$CONFIGMAPS${NC}"

# Check for potential issues
echo -e "\n${YELLOW}Potential Issues:${NC}"

# Check for pods not running
NOT_RUNNING=$(kubectl get pods -A | grep -v "Running" | grep -v "Completed" | wc -l)
if [ $NOT_RUNNING -gt 1 ]; then
    echo -e "${RED}Warning: $NOT_RUNNING pods not in Running state${NC}"
fi

# Check for pending PVCs
PENDING_PVC=$(kubectl get pvc -A | grep "Pending" | wc -l)
if [ $PENDING_PVC -gt 0 ]; then
    echo -e "${RED}Warning: $PENDING_PVC PVCs in Pending state${NC}"
fi

# Check for failed jobs
FAILED_JOBS=$(kubectl get jobs -A | grep "0/1" | wc -l)
if [ $FAILED_JOBS -gt 0 ]; then
    echo -e "${RED}Warning: $FAILED_JOBS failed jobs found${NC}"
fi

echo -e "\n${GREEN}Code review checks completed.${NC}"
echo "Please review the output and address any issues found."
echo "For detailed analysis, refer to docs/code-review.md" 