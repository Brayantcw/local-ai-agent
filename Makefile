.PHONY: all deploy-infra deploy-agent deploy-security deploy-observability deploy-ingress clean

CLUSTER_NAME=ai-agent-cluster
NAMESPACE_AGENT=ai-agent
NAMESPACE_LLM=llm-serving
NAMESPACE_OBSERVABILITY=observability
NAMESPACE_SECURITY=security

all: deploy-infra deploy-security deploy-observability deploy-ingress deploy-agent

# --- Namespaces ---
namespaces:
	kubectl apply -f k8s/namespaces/

# --- Infrastructure ---
deploy-infra: namespaces
	@echo ">>> Deploying Ollama (LLM Inference)..."
	kubectl apply -f k8s/ollama/
	@echo ">>> Waiting for Ollama to be ready..."
	kubectl wait --for=condition=ready pod -l app=ollama -n $(NAMESPACE_LLM) --timeout=300s
	@echo ">>> Pulling Gemma 4 E4B model (9.6GB, may take a few minutes)..."
	kubectl exec -n $(NAMESPACE_LLM) deploy/ollama -- ollama pull gemma4:e2b

# --- Ingress (Traefik) ---
deploy-ingress: namespaces
	@echo ">>> Deploying Traefik Ingress Controller..."
	helm repo add traefik https://traefik.github.io/charts || true
	helm repo update
	helm upgrade --install traefik traefik/traefik \
		-n traefik --create-namespace \
		-f helm-values/traefik.yaml
	@echo ">>> Applying Ingress rules..."
	kubectl apply -f k8s/ingress/

# --- Security ---
deploy-security: namespaces
	@echo ">>> Deploying Kyverno..."
	helm repo add kyverno https://kyverno.github.io/kyverno/ || true
	helm repo update
	helm upgrade --install kyverno kyverno/kyverno \
		-n kyverno --create-namespace \
		-f helm-values/kyverno.yaml
	@echo ">>> Waiting for Kyverno CRDs to be ready..."
	kubectl wait --for=condition=established crd/clusterpolicies.kyverno.io --timeout=120s
	@echo ">>> Waiting for Kyverno pods to be ready..."
	kubectl wait --for=condition=ready pod -l app.kubernetes.io/instance=kyverno -n kyverno --timeout=120s
	@echo ">>> Applying network policies..."
	kubectl apply -f k8s/security/network-policies.yaml
	@echo ">>> Applying Kyverno policies..."
	kubectl apply -f k8s/security/kyverno-policies.yaml

# --- Observability ---
deploy-observability: namespaces
	@echo ">>> Deploying Prometheus + Grafana..."
	helm repo add prometheus-community https://prometheus-community.github.io/helm-charts || true
	helm repo update
	helm upgrade --install kube-prometheus prometheus-community/kube-prometheus-stack \
		-n $(NAMESPACE_OBSERVABILITY) \
		-f helm-values/prometheus-stack.yaml
	@echo ">>> Deploying Grafana dashboard and ServiceMonitor..."
	kubectl apply -f k8s/observability/

# --- Agent ---
deploy-agent: namespaces
	@echo ">>> Building agent image..."
	docker build -t ai-agent:latest ./agent
	@echo ">>> Loading image into kind cluster..."
	kind load docker-image ai-agent:latest --name ai-agent-cluster
	@echo ">>> Deploying AI Agent..."
	kubectl apply -f k8s/agent/

# --- Cleanup ---
clean:
	kubectl delete -f k8s/ingress/ --ignore-not-found
	kubectl delete -f k8s/agent/ --ignore-not-found
	kubectl delete -f k8s/ollama/ --ignore-not-found
	kubectl delete -f k8s/security/ --ignore-not-found
	helm uninstall traefik -n traefik || true
	helm uninstall kube-prometheus -n $(NAMESPACE_OBSERVABILITY) || true
	helm uninstall kyverno -n kyverno || true
	kubectl delete -f k8s/namespaces/ --ignore-not-found

# --- Helpers ---
port-forward-grafana:
	kubectl port-forward -n $(NAMESPACE_OBSERVABILITY) svc/kube-prometheus-grafana 3000:80

port-forward-agent:
	kubectl port-forward -n $(NAMESPACE_AGENT) svc/ai-agent 8000:8000

port-forward-ollama:
	kubectl port-forward -n $(NAMESPACE_LLM) svc/ollama 11434:11434

logs-agent:
	kubectl logs -n $(NAMESPACE_AGENT) -l app=ai-agent -f

logs-ollama:
	kubectl logs -n $(NAMESPACE_LLM) -l app=ollama -f

# --- Cluster Management ---
create-cluster:
	./scripts/setup-kind.sh

delete-cluster:
	kind delete cluster --name $(CLUSTER_NAME)
