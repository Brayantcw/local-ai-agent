#!/bin/bash
set -euo pipefail

echo "=== Testing AI Agent ==="

BASE_URL="${1:-http://ai-agent.local}"

echo ">>> Health check..."
curl -sf "${BASE_URL}/health" | python3 -m json.tool

echo ""
echo ">>> List models..."
curl -sf "${BASE_URL}/api/v1/models" | python3 -m json.tool

echo ""
echo ">>> Chat test..."
curl -sf -X POST "${BASE_URL}/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "What is Kubernetes in one sentence?"}' | python3 -m json.tool

echo ""
echo "=== All tests passed ==="
