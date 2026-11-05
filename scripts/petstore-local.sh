#!/usr/bin/env bash
# A local Swagger Petstore for the before side, seeded with the demo's four pets (Rex, Mia, Bello, Max sold).
# Usage: scripts/petstore-local.sh start|stop|status|logs
# Every start is a fresh container, seeded again: that is the reset between evaluation runs.
set -euo pipefail

NAME=petstore-local
IMAGE=swaggerapi/petstore3:1.0.29   # same version as the pinned spec; amd64 only (emulated on arm64)
PORT=${LOCAL_PETSTORE_PORT:-8081}  # 8080 is Keycloak, 8082 the kagent UI
URL="http://localhost:$PORT/api/v3"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

running() { [ "$(docker inspect -f '{{.State.Running}}' "$NAME" 2>/dev/null)" = "true" ]; }

start() {
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  docker run -d --name "$NAME" --platform linux/amd64 -p "$PORT:8080" "$IMAGE" >/dev/null
  printf 'Waiting for the local Petstore'
  for _ in $(seq 1 90); do
    if curl -fsS "$URL/pet/1" >/dev/null 2>&1; then
      echo; (cd "$ROOT" && uv run python eval.py seed --url "$URL"); return
    fi
    printf '.'; sleep 1
  done
  echo; echo "The local Petstore did not come up; see: $0 logs" >&2; exit 1
}

stop() {
  if docker inspect "$NAME" >/dev/null 2>&1; then docker rm -f "$NAME" >/dev/null; echo "$NAME stopped"
  else echo "$NAME not running"; fi
}

case "${1:-}" in
  start) start ;;
  stop) stop ;;
  status) running && echo "$NAME running: $URL" || { echo "$NAME not running"; exit 1; } ;;
  logs) docker logs -f "$NAME" ;;
  *) echo "usage: $0 start|stop|status|logs" >&2; exit 2 ;;
esac
