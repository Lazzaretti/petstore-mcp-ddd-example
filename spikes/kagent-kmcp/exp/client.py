import asyncio
import json
import sys

import urllib.request
from fastmcp import Client
from fastmcp.client.elicitation import ElicitResult

BASE = "http://127.0.0.1:8799"


async def handler(message, response_type, params, ctx):
    print("  elicitation message:", message)
    print("  requestedSchema:", json.dumps(params.requested_schema))
    return ElicitResult(action="accept", content=response_type(value="Sat 14:00"))


async def run(mode):
    print(f"=== mode={mode}")
    for name in ["discovery", "sales", "handover"]:
        async with Client(f"{BASE}/{name}/mcp", mode=mode, elicitation_handler=handler) as c:
            tools = await c.list_tools()
            print(name, [(t.name, t.annotations.readOnlyHint if t.annotations else None) for t in tools])
            if name == "sales":
                res = await c.list_resources()
                print("  resources:", [str(r.uri) for r in res])
                r = await c.read_resource("pet-sales://policies")
                print("  policies:", r[0].text[:30])
                out = await c.call_tool("buy_pet", {"pet_id": "rex"})
                print("  buy_pet ->", out.data)


async def main():
    if True:
        print("GET /sales/stock", urllib.request.urlopen(f"{BASE}/sales/stock").read().decode())
    for mode in sys.argv[1:] or ["auto", "legacy"]:
        await run(mode)


asyncio.run(main())
