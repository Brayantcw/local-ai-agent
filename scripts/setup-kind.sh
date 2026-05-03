#!/bin/bash
set -euo pipefail

CLUSTER_NAME="ai-agent-cluster"

echo "=== Setting up kind cluster for AI Agent ==="

# Check prerequisites
command -v kind >/dev/null 2>&1 || { echo "kind not found. Install: brew install kind"; exit 1; }
command -v kubectl >/dev/null 2>&1 || { echo "kubectl not found. Install it first."; exit 1; }
command -v helm >/dev/null 2>&1 || { echo "helm not found. Install it first."; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "docker not found. Install Docker Desktop first."; exit 1; }

# Check if cluster already exists
if kind get clusters 2>/dev/null | grep -q "^${CLUSTER_NAME}$"; then
    echo ">>> Cluster '${CLUSTER_NAME}' already exists"
else
    echo ">>> Creating 3-node kind cluster..."
    kind create cluster --name "${CLUSTER_NAME}" --config "$(dirname "$0")/../k8s/kind/cluster-config.yaml"
fi

# Set kubectl context
kubectl cluster-info --context "kind-${CLUSTER_NAME}"

# Install metrics-server (kind doesn't have it by default)
echo ">>> Installing metrics-server..."
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml || true
# Patch for kind (no TLS verification needed locally)
kubectl patch deployment metrics-server -n kube-system \
  --type='json' \
  -p='[{"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"}]' 2>/dev/null || true

# Add /etc/hosts entry for ingress
if ! grep -q "ai-agent.local" /etc/hosts; then
    echo ">>> Adding ai-agent.local to /etc/hosts (requires sudo)..."
    echo "127.0.0.1 ai-agent.local" | sudo tee -a /etc/hosts
else
    echo ">>> ai-agent.local already in /etc/hosts"
fi

echo ""
echo "=== Setup Complete ==="
echo "Cluster: ${CLUSTER_NAME} (3 nodes)"
echo "Context: kind-${CLUSTER_NAME}"
echo ""
echo "Next steps:"
echo "  1. make deploy-infra"
echo "  2. make deploy-security"
echo "  3. make deploy-ingress"
echo "  4. make deploy-agent"
echo "  5. curl http://localhost:30080/api/v1/chat -d '{\"message\": \"hello\"}' -H 'Content-Type: application/json'"
