#!/usr/bin/env bash
# kind + kagent 0.10.4 with the three servers as RemoteMCPServers, for the kagent screenshot.
# Usage: scripts/kagent-kind.sh up|status|ui|down
#   up:     kind cluster `petstore`, kagent via Helm (never `kagent install`), the three RemoteMCPServers
#   ui:     kagent UI on http://localhost:8082 (View → "MCP & tools", filter "petstore")
# The app must run with AUTH=off on 0.0.0.0:8000 (kagent can't do the OAuth flow):
#   AUTH=off uv run python -m petstore.app serve
set -euo pipefail

CLUSTER=petstore
VERSION=0.10.4
CHARTS=oci://ghcr.io/kagent-dev/kagent/helm
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# kind runs inside this container's Docker-in-Docker: its network's gateway is this container,
# where the app listens. host.docker.internal would point at the Mac instead.
gateway() {
  docker network inspect kind | jq -r '.[0].IPAM.Config[] | select(.Gateway | test("^[0-9.]+$")) | .Gateway' | head -1
}

up() {
  kind get clusters | grep -qx "$CLUSTER" || kind create cluster --name "$CLUSTER"
  helm upgrade --install kagent-crds "$CHARTS/kagent-crds" --version "$VERSION" -n kagent --create-namespace --wait
  helm upgrade --install kagent "$CHARTS/kagent" --version "$VERSION" -n kagent \
    -f "$ROOT/k8s/kagent-values.yaml" --wait --timeout 10m
  APP_URL="http://$(gateway):8000" envsubst < "$ROOT/k8s/remote-mcp-servers.yaml" | kubectl apply -f -
  status
}

status() {
  echo "App URL for kagent: http://$(gateway):8000"
  kubectl -n kagent get remotemcpservers
}

ui() {
  echo "kagent UI: http://localhost:8082"
  kubectl -n kagent port-forward svc/kagent-ui 8082:8080
}

down() { kind delete cluster --name "$CLUSTER"; }

case "${1:-}" in
  up) up ;;
  status) status ;;
  ui) ui ;;
  down) down ;;
  *) echo "usage: $0 up|status|ui|down" >&2; exit 2 ;;
esac
