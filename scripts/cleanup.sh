#!/bin/bash

# Set default values
NAMESPACE="developer-platform"
OLDER_THAN="7d"
DRY_RUN=true

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --namespace)
      NAMESPACE="$2"
      shift 2
      ;;
    --older-than)
      OLDER_THAN="$2"
      shift 2
      ;;
    --execute)
      DRY_RUN=false
      shift
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# Function to run kubectl with or without dry-run
kubectl_cmd() {
  if [ "$DRY_RUN" = true ]; then
    kubectl "$@" --dry-run=client
  else
    kubectl "$@"
  fi
}

echo "Cleaning up resources in namespace: $NAMESPACE"
echo "Removing resources older than: $OLDER_THAN"
if [ "$DRY_RUN" = true ]; then
  echo "DRY RUN MODE: No changes will be made"
fi

# Find and delete old PVCs
echo "Finding old PVCs..."
OLD_PVCS=$(kubectl get pvc -n "$NAMESPACE" -o json | jq -r ".items[] | select(.metadata.creationTimestamp | fromdateiso8601 < (now - (${OLDER_THAN%d} * 86400))) | .metadata.name")
for pvc in $OLD_PVCS; do
  echo "Deleting PVC: $pvc"
  kubectl_cmd delete pvc "$pvc" -n "$NAMESPACE"
done

# Find and delete completed/failed pods
echo "Finding completed/failed pods..."
OLD_PODS=$(kubectl get pods -n "$NAMESPACE" -o json | jq -r '.items[] | select(.status.phase as $phase | ["Succeeded", "Failed"] | index($phase)) | .metadata.name')
for pod in $OLD_PODS; do
  echo "Deleting pod: $pod"
  kubectl_cmd delete pod "$pod" -n "$NAMESPACE"
done

# Clean up old images in Artifact Registry
if [ "$DRY_RUN" = false ]; then
  echo "Cleaning up old container images..."
  gcloud container images list-tags \
    "gcr.io/$PROJECT_ID/developer-platform/vscode-jupyter" \
    --format="get(digest)" \
    --filter="timestamp.datetime < -P${OLDER_THAN}" \
    | while read -r digest; do
        gcloud container images delete \
          "gcr.io/$PROJECT_ID/developer-platform/vscode-jupyter@$digest" \
          --quiet
      done
fi

 