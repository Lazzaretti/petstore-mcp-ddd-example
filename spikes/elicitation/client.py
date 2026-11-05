"""FastMCP client: calls buy_pet, elicitation handler picks first option (or declines/cancels).

Usage: .venv/bin/python client.py [auto|legacy] [accept|decline|cancel|none]
  auto   -> negotiates 2026-07-28 (server/discover), input_required round trip
  legacy -> initialize handshake (2025-11-25), server-initiated elicitation/create
  none   -> no elicitation_handler (client does not declare the capability)
"""

import asyncio
import sys

from fastmcp import Client
from fastmcp.client.elicitation import ElicitResult

URL = "http://127.0.0.1:8765/mcp"
mode = sys.argv[1] if len(sys.argv) > 1 else "auto"
behaviour = sys.argv[2] if len(sys.argv) > 2 else "accept"


async def handler(message, response_type, params, context):
    schema = params.requested_schema
    print("ELICIT message:", message)
    print("ELICIT schema :", schema)
    if behaviour != "accept":
        return ElicitResult(action=behaviour)
    # one property: "pickup_slot" (our 2026-07-28 schema) or "value" (ctx.elicit wrapper)
    (field, prop), = schema["properties"].items()
    first = prop["oneOf"][0]["const"] if "oneOf" in prop else prop["enum"][0]
    print("ELICIT choose :", field, "=", first)
    return {field: first}


async def main():
    kw = {} if behaviour == "none" else {"elicitation_handler": handler}
    async with Client(URL, mode=mode, **kw) as c:
        print("protocol:", getattr(c, "protocol_version", None) or "?")
        res = await c.call_tool("buy_pet", {"pet_id": 1}, raise_on_error=False)
        print("RESULT:", res.is_error, [getattr(b, "text", b) for b in res.content])


asyncio.run(main())
