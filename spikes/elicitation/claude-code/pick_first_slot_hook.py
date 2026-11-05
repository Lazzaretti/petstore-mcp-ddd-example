#!/usr/bin/env python3
"""Claude Code Elicitation hook: answers a form request by picking the first enum/oneOf option."""
import json, sys
inp = json.load(sys.stdin)
open(__file__.replace(".py", ".input.json"), "w").write(json.dumps(inp, indent=2))
schema = inp.get("requested_schema") or {}
content = {}
for name, prop in schema.get("properties", {}).items():
    if "oneOf" in prop:
        content[name] = prop["oneOf"][0]["const"]
    elif "enum" in prop:
        content[name] = prop["enum"][0]
print(json.dumps({"hookSpecificOutput": {"hookEventName": "Elicitation",
                                         "action": "accept", "content": content}}))
