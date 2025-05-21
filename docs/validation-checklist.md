# End-to-End Validation Checklist

## 1. Infrastructure Validation

### GCP Resources
- [ ] Project setup
  ```bash
  # Verify project and APIs
  gcloud projects describe $PROJECT_ID
  gcloud services list --enabled
  ```
- [ ] VPC and networking
  ```bash
  # Check VPC and subnets
  gcloud compute networks list
  gcloud compute networks subnets list
  ```
- [ ] GKE cluster
  ```bash
  # Verify cluster status
  gcloud container clusters list
  gcloud container clusters describe $CLUSTER_NAME
  ```
- [ ] IAM and service accounts
  ```bash
  # Check service accounts and roles
  gcloud iam service-accounts list
  gcloud projects get-iam-policy $PROJECT_ID
  ```

### Storage Setup
- [ ] GCS buckets
  ```bash
  # Verify buckets and permissions
  gsutil ls
  gsutil iam get gs://${BUCKET_NAME}
  ```
- [ ] Versioning configuration
  ```bash
  # Check versioning status
  gsutil versioning get gs://${BUCKET_NAME}
  gsutil lifecycle get gs://${BUCKET_NAME}
  ```

## 2. Kubernetes Components

### Core Services
- [ ] Namespace setup
  ```bash
  kubectl get ns
  kubectl describe ns developer-platform
  ```
- [ ] RBAC configuration
  ```bash
  kubectl get clusterroles,clusterrolebindings | grep jupyter
  kubectl describe clusterrole jupyter-user
  kubectl describe clusterrole jupyter-admin
  ```
- [ ] Storage classes
  ```bash
  kubectl get sc
  kubectl describe sc gcsfuse-versioned
  ```

### Label Management
- [ ] Standard Labels
  ```bash
  # Verify standard labels across resources
  kubectl get all -l app.kubernetes.io/part-of=developer-platform -A
  kubectl get all -l environment=${ENV} -A
  ```
- [ ] Component Labels
  ```bash
  # Check component-specific resources
  kubectl get all -l app.kubernetes.io/component=ingress -A
  kubectl get all -l app.kubernetes.io/name=jupyterhub -n developer-platform
  kubectl get all -l app.kubernetes.io/name=grafana -n monitoring
  ```
- [ ] Service Selection
  ```bash
  # Verify service selector matching
  kubectl get pods -l app.kubernetes.io/name=jupyterhub -n developer-platform --show-labels
  kubectl get svc -l app.kubernetes.io/name=jupyterhub -n developer-platform -o wide
  ```
- [ ] Monitoring Labels
  ```bash
  # Check Prometheus service discovery
  kubectl get servicemonitors -A
  kubectl get pods -l prometheus.io/scrape=true -A
  ```
- [ ] Label Consistency
  ```bash
  # Audit label usage
  kubectl describe nodes | grep -A5 Labels
  kubectl get ns --show-labels
  kubectl get all -A -o json | jq '.items[].metadata.labels'
  ```

### Ingress Configuration
- [ ] Ingress Controller
  ```bash
  # Verify ingress controller is running
  kubectl get pods -n ingress-nginx
  kubectl get svc -n ingress-nginx
  ```
- [ ] Ingress Rules
  ```bash
  # Check ingress configurations
  kubectl get ingress -A
  kubectl describe ingress -n developer-platform jupyter-ingress
  kubectl describe ingress -n monitoring grafana-ingress
  ```
- [ ] DNS Resolution
  ```bash
  # Verify DNS records
  nslookup jupyter.${DOMAIN}
  nslookup grafana.${DOMAIN}
  ```
- [ ] SSL/TLS Status
  ```bash
  # Check SSL certificates
  kubectl get certificates -n developer-platform
  kubectl get secrets -n developer-platform | grep tls
  ```
- [ ] Connectivity Test
  ```bash
  # Test endpoints
  curl -I https://jupyter.${DOMAIN}/hub/health
  curl -I https://grafana.${DOMAIN}/api/health
  ```

### Application Deployments
- [ ] JupyterHub
  ```bash
  kubectl -n developer-platform get all -l app=jupyterhub
  kubectl -n developer-platform describe deployment jupyterhub
  ```
- [ ] ArgoCD
  ```bash
  kubectl -n argocd get all
  argocd app list
  ```
- [ ] Monitoring stack
  ```bash
  kubectl -n monitoring get all
  kubectl -n monitoring get servicemonitors
  ```

## 3. Authentication & Security

### OIDC Setup
- [ ] Google OAuth configuration
  ```bash
  # Verify OAuth secret
  kubectl -n developer-platform get secret oauth-secret -o yaml
  ```
- [ ] JupyterHub auth config
  ```bash
  kubectl -n developer-platform get cm jupyterhub-oidc-config -o yaml
  ```
- [ ] Test authentication flow
  ```bash
  # Access URLs and verify redirects
  curl -I https://jupyter.${DOMAIN}/hub/login
  ```

### TLS/Certificates
- [ ] cert-manager status
  ```bash
  kubectl get certificates,certificaterequests,orders,challenges -A
  ```
- [ ] SSL verification
  ```bash
  openssl s_client -connect jupyter.${DOMAIN}:443 -servername jupyter.${DOMAIN}
  ```

## 4. User Environment

### Resource Profiles
- [ ] Standard environment
  ```bash
  # Test pod creation
  kubectl -n developer-platform create -f test/manifests/standard-pod.yaml
  ```
- [ ] High-memory environment
  ```bash
  # Verify resource limits
  kubectl -n developer-platform describe resourcequota
  ```
- [ ] GPU environment
  ```bash
  # Check GPU availability
  kubectl get nodes -l cloud.google.com/gke-nodepool=gpu
  ```

### Storage Access
- [ ] PVC provisioning
  ```bash
  # Test PVC creation
  kubectl -n developer-platform create -f test/manifests/test-pvc.yaml
  ```
- [ ] GCS integration
  ```bash
  # Verify GCS mount
  kubectl -n developer-platform exec test-pod -- df -h /workspace
  ```

## 5. Monitoring & Logging

### Prometheus/Grafana
- [ ] Metrics collection
  ```bash
  # Check Prometheus targets
  curl -s http://prometheus:9090/api/v1/targets | jq
  ```
- [ ] Dashboard access
  ```bash
  # Verify Grafana login
  curl -I https://grafana.${DOMAIN}
  ```

### Logging
- [ ] Application logs
  ```bash
  # Check log shipping
  kubectl logs -l app=fluentd -n logging
  ```
- [ ] Audit logs
  ```bash
  # Verify audit policy
  kubectl get auditpolicy default -o yaml
  ```

## 6. Backup & Disaster Recovery

### Backup Systems
- [ ] GCS versioning
  ```bash
  # Test version access
  gsutil ls gs://${BUCKET_NAME}/.versions/
  ```
- [ ] Cluster backup
  ```bash
  # Verify etcd backup
  gcloud container clusters describe $CLUSTER_NAME \
    --format='get(etcdBackup)'
  ```

### Recovery Procedures
- [ ] Version restoration
  ```bash
  # Test file recovery
  gsutil cp gs://${BUCKET_NAME}/.versions/test-file_* ./test-file
  ```
- [ ] Pod recreation
  ```bash
  # Test pod recovery
  kubectl -n developer-platform delete pod test-pod
  kubectl -n developer-platform wait --for=condition=Ready pod/test-pod
  ```

## 7. CI/CD Pipeline

### GitHub Actions
- [ ] Workflow status
  ```bash
  # Check recent workflows
  gh run list -L 5
  ```
- [ ] Build process
  ```bash
  # Verify image builds
  docker build -t test-image .
  ```

### ArgoCD Sync
- [ ] Application sync
  ```bash
  # Check sync status
  argocd app get developer-platform
  argocd app sync developer-platform
  ```

## 8. Performance Testing

### Load Testing
- [ ] JupyterHub spawner
  ```bash
  # Run load test
  k6 run load-tests/spawner-test.js
  ```
- [ ] Storage performance
  ```bash
  # Test I/O performance
  kubectl -n developer-platform exec test-pod -- fio storage-benchmark.fio
  ```

### Resource Utilization
- [ ] Node metrics
  ```bash
  kubectl top nodes
  ```
- [ ] Pod metrics
  ```bash
  kubectl top pods -A
  ```

## 9. Documentation

### User Documentation
- [ ] Quick start guide
- [ ] Environment setup
- [ ] Storage management
- [ ] Troubleshooting guide

### Developer Documentation
- [ ] API reference
- [ ] Development setup
- [ ] Contributing guidelines
- [ ] Architecture overview

## 10. Cleanup & Reset

### Resource Cleanup
- [ ] Remove test resources
  ```bash
  kubectl delete -f test/manifests/
  ```
- [ ] Clear test data
  ```bash
  gsutil rm -r gs://${BUCKET_NAME}/test-*
  ```

### Environment Reset
- [ ] Reset configurations
  ```bash
  kubectl delete cm test-config
  kubectl apply -f k8s/base/configmaps/
  ```
- [ ] Restart services
  ```bash
  kubectl -n developer-platform rollout restart deployment jupyterhub
  ``` 