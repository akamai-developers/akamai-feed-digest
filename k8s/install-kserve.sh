#!/usr/bin/env bash
set -euo pipefail

# Install KServe and its dependencies on an LKE cluster
# Run this once before deploy.sh

if [ -z "${KUBECONFIG:-}" ]; then
  echo "Error: KUBECONFIG is not set"
  echo "Usage: export KUBECONFIG=\$(pwd)/terraform/kubeconfig.yaml"
  exit 1
fi

echo "=== Installing cert-manager ==="
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.17.2/cert-manager.yaml
echo "Waiting for cert-manager to be ready..."
kubectl wait --for=condition=Available deployment --all -n cert-manager --timeout=120s

echo ""
echo "=== Installing Knative Serving ==="
kubectl apply -f https://github.com/knative/serving/releases/download/knative-v1.17.0/serving-crds.yaml
kubectl apply -f https://github.com/knative/serving/releases/download/knative-v1.17.0/serving-core.yaml
echo "Waiting for Knative Serving to be ready..."
kubectl wait --for=condition=Available deployment --all -n knative-serving --timeout=120s

echo ""
echo "=== Installing Kourier (networking layer) ==="
kubectl apply -f https://github.com/knative/net-kourier/releases/download/knative-v1.17.0/kourier.yaml
echo "Waiting for Kourier to be ready..."
kubectl wait --for=condition=Available deployment --all -n kourier-system --timeout=120s

# Configure Knative to use Kourier
kubectl patch configmap/config-network \
  --namespace knative-serving \
  --type merge \
  --patch '{"data":{"ingress-class":"kourier.ingress.networking.knative.dev"}}'

# Enable nodeSelector support (required for GPU node targeting)
kubectl patch configmap/config-features \
  --namespace knative-serving \
  --type merge \
  --patch '{"data":{"kubernetes.podspec-nodeselector":"enabled"}}'

echo ""
echo "=== Installing KServe ==="
kubectl apply --server-side --force-conflicts -f https://github.com/kserve/kserve/releases/download/v0.14.1/kserve.yaml
echo "Waiting for KServe to be ready..."
kubectl wait --for=condition=Available deployment --all -n kserve --timeout=120s

kubectl apply -f https://github.com/kserve/kserve/releases/download/v0.14.1/kserve-cluster-resources.yaml

echo ""
echo "=== KServe installation complete ==="
echo "Verify with:"
echo "  kubectl get pods -n kserve"
echo "  kubectl get pods -n knative-serving"
echo "  kubectl get pods -n kourier-system"
