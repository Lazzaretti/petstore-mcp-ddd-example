#!/usr/bin/env bash
# Before every take of the before clip: the local Petstore back to the seed (Rex, Mia, Bello
# available, Max sold), checked, and stage-before/ trusted so Claude Code shows no trust dialog.
# Same reset as the evaluation: a fresh container, seeded again (no orders or added pets survive).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
URL="http://localhost:${LOCAL_PETSTORE_PORT:-8081}/api/v3"
CONFIG="${CLAUDE_CONFIG_DIR:-$HOME}/.claude.json"
[ -f "$CONFIG" ] || CONFIG="$HOME/.claude.json"

"$ROOT/scripts/petstore-local.sh" start >/dev/null

expect() {  # pet id, name, status
  local pet; pet="$(curl -fsS "$URL/pet/$1")"
  [ "$(jq -r '.name + " " + .status' <<<"$pet")" = "$2 $3" ] || { echo "pet $1 is not $2 ($3): $pet" >&2; exit 1; }
}
expect 1 Rex available; expect 2 Mia available; expect 3 Bello available; expect 4 Max sold
[ "$(curl -fsS "$URL/pet/findByStatus?status=available" | jq length)" = 3 ] || { echo "extra pets on offer" >&2; exit 1; }

if [ -f "$CONFIG" ]; then
  tmp="$(mktemp)"
  jq --arg dir "$ROOT/stage-before" '.projects[$dir] = ((.projects[$dir] // {}) + {hasTrustDialogAccepted: true})' \
    "$CONFIG" >"$tmp" && cat "$tmp" >"$CONFIG" && rm -f "$tmp"
fi
echo "Local Petstore reset: Rex, Mia, Bello available, Max sold ($URL)"
