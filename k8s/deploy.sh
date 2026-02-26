#!/usr/bin/env bash
set -euo pipefail

# Deploy feed-digest app to LKE cluster
# Requires: DOCKERHUB_USER, DATABASE_URL, and KUBECONFIG to be set

if [ -z "${DOCKERHUB_USER:-}" ]; then
  echo "Error: DOCKERHUB_USER is not set"
  echo "Usage: export DOCKERHUB_USER=your-dockerhub-username"
  exit 1
fi

if [ -z "${DATABASE_URL:-}" ]; then
  echo "Error: DATABASE_URL is not set"
  echo "Usage: export DATABASE_URL=\$(cd terraform && terraform output -raw database_url)"
  exit 1
fi

if [ -z "${KUBECONFIG:-}" ]; then
  echo "Error: KUBECONFIG is not set"
  echo "Usage: export KUBECONFIG=\$(pwd)/terraform/kubeconfig.yaml"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Deploying with DOCKERHUB_USER=${DOCKERHUB_USER}"
echo "Using KUBECONFIG=${KUBECONFIG}"

for f in "$SCRIPT_DIR"/*.yaml; do
  envsubst < "$f"
  echo "---"
done | kubectl apply -f -

echo ""
echo "Waiting for external IP..."
kubectl get svc app-service -n feed-digest
