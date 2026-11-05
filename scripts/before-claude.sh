#!/usr/bin/env bash
# Interactive Claude Code on the before side only, set up like the evaluation (eval.py): only the
# wrapped Petstore (stage-before/.mcp.json, strict), no built-in tools, only stage-before's settings
# (all petstore tools pre-allowed, no CLAUDE.md), the same effort and appended system prompt.
# CUSTOMER=answers: no appended system prompt, the customer answers (like scripts/after-claude.sh).
set -euo pipefail
cd "$(dirname "$0")/../stage-before"
args=()
if [ "${CUSTOMER:-}" != answers ]; then
  args=(--append-system-prompt "The customer is not available to answer questions during this run. Where you would ask them, decide yourself with the first sensible option and say what you chose.")
fi
exec claude --model "${MODEL:-claude-opus-5-5}" --effort medium --permission-mode default \
  --strict-mcp-config --mcp-config .mcp.json --setting-sources project --tools "" ${args[@]+"${args[@]}"}
