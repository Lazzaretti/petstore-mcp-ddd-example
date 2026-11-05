#!/usr/bin/env bash
# Renders takes of the before clip with VHS: media/before-clip-take<n>.mp4, the frame after
# prompt (1) as media/before-clip-take<n>-done.png, and what happened as media/before-clip-take<n>.json.
# Usage: media/render-before-clip.sh [first take] [last take]   (default 1 3)
# Model: Haiku 4.5 by default (MODEL=… for another). Another tape or output: TAPE=…, OUT=… (prefix).
# A clean environment (env -i): nothing from a surrounding Claude Code session (child-session
# marker, IDE connection) leaks into the recorded one. DISABLE_AUTOUPDATER stays: without it Claude Code
# updates itself mid-take (4 Nov: 2.1.316 -> 2.1.318, banner on screen).
set -euo pipefail
cd "$(dirname "$0")/.."

TAPE="${TAPE:-media/before-clip.tape}"
OUT="${OUT:-media/before-clip-take}"   # take n -> $OUT<n>.mp4, $OUT<n>-done.png, $OUT<n>.json
mkdir -p "$(dirname "$OUT")"

for take in $(seq "${1:-1}" "${2:-${1:-3}}"); do
  tape="$(mktemp --suffix=.tape)"
  sed -e "s#^Output .*#Output $OUT$take.mp4#" \
      -e "s#^Screenshot media/before-clip-done.png#Screenshot $OUT$take-done.png#" \
      "$TAPE" >"$tape"
  echo "== take $take"
  env -i HOME="$HOME" PATH="$PATH" LANG=C.UTF-8 TERM=xterm-256color DISABLE_AUTOUPDATER=1 MODEL="${MODEL:-claude-haiku-4-5}" \
    CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}" vhs "$tape" >/dev/null
  rm -f "$tape"
  PYTHONPATH=. uv run python scripts/check_before_take.py --out "$OUT$take.json"
  ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT$take.mp4" \
    | awk '{printf "duration: %.1f s\n", $1}'
done
