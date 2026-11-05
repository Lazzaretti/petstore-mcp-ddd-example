#!/usr/bin/env bash
# Interactive Claude Code on the after side only: the three domain servers (stage-after/.mcp.json,
# strict), no built-in tools, only stage-after's settings (reads pre-allowed, writes ask, no CLAUDE.md),
# the same model and effort as the before clip. No appended system prompt: here the customer answers.
set -euo pipefail
cd "$(dirname "$0")/../stage-after"
exec claude --model "${MODEL:-claude-opus-5-5}" --effort medium --permission-mode default \
  --strict-mcp-config --mcp-config .mcp.json --setting-sources project --tools ""
