#!/usr/bin/env bash
# Keycloak for the demo: realm `petstore` (users alice/bob), issuer http://localhost:8080/realms/petstore.
# Usage: scripts/keycloak.sh start|stop|status|logs
# start-dev keeps everything in the container: `stop` removes it, the next `start` re-imports the realm.
# Local dev credentials only (admin/admin, alice-demo, bob-demo); never use them anywhere else.
set -euo pipefail

NAME=petstore-keycloak
IMAGE=quay.io/keycloak/keycloak:26.8.1
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REALM="$ROOT/spikes/keycloak/petstore-realm.json"   # moves to the demo code later
ISSUER=http://localhost:8080/realms/petstore

running() { [ "$(docker inspect -f '{{.State.Running}}' "$NAME" 2>/dev/null)" = "true" ]; }

start() {
  if running; then echo "$NAME already running: $ISSUER"; return; fi
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  docker run -d --name "$NAME" -p 8080:8080 \
    -e KC_HOSTNAME=http://localhost:8080 \
    -e KC_BOOTSTRAP_ADMIN_USERNAME=admin -e KC_BOOTSTRAP_ADMIN_PASSWORD=admin \
    -v "$REALM:/opt/keycloak/data/import/petstore-realm.json:ro" \
    "$IMAGE" start-dev --features=cimd,resource-indicators --import-realm >/dev/null
  printf 'Waiting for Keycloak'
  for _ in $(seq 1 90); do
    if curl -fsS "$ISSUER/.well-known/openid-configuration" >/dev/null 2>&1; then
      echo; echo "$NAME up: $ISSUER (admin console http://localhost:8080/admin, admin/admin)"; return
    fi
    printf '.'; sleep 2
  done
  echo; echo "Keycloak did not come up; see: $0 logs" >&2; exit 1
}

stop() {
  if docker inspect "$NAME" >/dev/null 2>&1; then docker rm -f "$NAME" >/dev/null; echo "$NAME stopped"
  else echo "$NAME not running"; fi
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  status) running && echo "$NAME running: $ISSUER" || { echo "$NAME not running"; exit 1; } ;;
  logs) docker logs -f "$NAME" ;;
  *) echo "usage: $0 start|stop|status|logs" >&2; exit 2 ;;
esac
