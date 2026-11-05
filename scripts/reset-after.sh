#!/usr/bin/env bash
# Before every take of the after clip: a fresh app (reset = restart, the store is in memory) with the
# seed (Rex, Mia, Bello on offer, Max sold), checked, and stage-after/ trusted so Claude Code shows no
# trust dialog. Like the evaluation: AUTH=off as alice, port 8010 (not the stage app's 8000, whose
# OAuth state Claude Code caches per server name and URL). The clock is fixed at the talk's moment
# (Mon, Nov 9, 4:45 PM), so the free slots in the clip are the ones the audience would get on stage.
# Usage: scripts/reset-after.sh [stop]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PORT=8010
URL="http://localhost:$PORT"
PIDFILE="/tmp/petstore-after-clip.pid"
CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
CONFIG="$CONFIG_DIR/.claude.json"
[ -f "$CONFIG" ] || CONFIG="$HOME/.claude.json"

stop() {
  if [ -f "$PIDFILE" ]; then kill "$(cat "$PIDFILE")" 2>/dev/null || true; rm -f "$PIDFILE"; fi
  for _ in $(seq 1 50); do curl -fsS "$URL/sales/stock" >/dev/null 2>&1 || return 0; sleep 0.1; done
  echo "something still answers on port $PORT" >&2; exit 1
}

stop
[ "${1:-}" = stop ] && exit 0

cd "$ROOT"
AUTH=off PETSTORE_CUSTOMER=alice PICKUP=on PORT=$PORT PETSTORE_NOW=2026-11-09T16:45 \
  setsid nohup uv run python -m petstore.app serve >"/tmp/petstore-after-clip.log" 2>&1 &
echo $! >"$PIDFILE"
for _ in $(seq 1 100); do curl -fsS "$URL/sales/stock" >/dev/null 2>&1 && break; sleep 0.2; done

stock="$(curl -fsS "$URL/sales/stock")"
[ "$(jq -c '{available, sold}' <<<"$stock")" = '{"available":3,"sold":1}' ] || { echo "not the seed: $stock" >&2; exit 1; }

# Claude Code caches "needs auth" per server name; a stale entry would drop the AUTH=off servers.
cache="$CONFIG_DIR/mcp-needs-auth-cache.json"
if [ -f "$cache" ]; then
  tmp="$(mktemp)"
  jq 'del(."petstore-discovery", ."petstore-sales", ."petstore-handover")' "$cache" >"$tmp" && cat "$tmp" >"$cache" && rm -f "$tmp"
fi
if [ -f "$CONFIG" ]; then
  tmp="$(mktemp)"
  jq --arg dir "$ROOT/stage-after" '.projects[$dir] = ((.projects[$dir] // {}) + {hasTrustDialogAccepted: true})' \
    "$CONFIG" >"$tmp" && cat "$tmp" >"$CONFIG" && rm -f "$tmp"
fi
echo "After app reset: Rex, Mia, Bello on offer, Max sold ($URL, clock Mon, Nov 9, 4:45 PM)"
