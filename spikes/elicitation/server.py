"""Pet Sales MCP server: buy_pet elicits a pickup slot from a fixed list.

Serves both protocol eras with one tool:
  * 2026-07-28 (stateless): returns InputRequiredResult (resultType "input_required")
    and reads ctx.input_responses on the retry (Multi Round-Trip Requests, SEP-2322).
  * <= 2025-11-25 (handshake): server-initiated elicitation/create via ctx.elicit().
  * client without the elicitation capability: domain error that names the slots,
    caller retries with pickup_slot=... (the fallback).

Run:  .venv/bin/python server.py            (Streamable HTTP on :8765/mcp, wire log)
      .venv/bin/python server.py stdio
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import mcp_types
from fastmcp import Context, FastMCP
from fastmcp.exceptions import ToolError
from mcp_types import ElicitRequest, ElicitRequestFormParams, InputRequiredResult
from mcp_types.version import MODERN_PROTOCOL_VERSIONS

SLOTS = {  # value -> title (fixed list the shop offers)
    "2026-11-07T10:00": "Sat 7 Nov 10:00",
    "2026-11-07T15:00": "Sat 7 Nov 15:00",
    "2026-11-09T10:00": "Mon 9 Nov 10:00",
}
PICKUP_MESSAGE = "When do you want to pick up your pet? The shop offers these slots."

mcp = FastMCP("pet-sales")


def log(*a):
    print("[pet-sales]", *a, file=sys.stderr, flush=True)


def pickup_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "pickup_slot": {
                "type": "string",
                "title": "Pickup slot",
                "oneOf": [{"const": v, "title": t} for v, t in SLOTS.items()],
            }
        },
        "required": ["pickup_slot"],
    }


def complete(pet_id: int, slot: str) -> str:
    return f"Pet {pet_id} bought. Pickup: {SLOTS[slot]} ({slot})."


def client_can_elicit(ctx: Context) -> bool:
    try:
        caps = ctx.session.client_capabilities
    except Exception:  # noqa: BLE001
        caps = None
    return bool(caps and caps.elicitation is not None)


@mcp.tool
async def buy_pet(
    pet_id: int,
    ctx: Context,
    reservation_id: str | None = None,
    pickup_slot: str | None = None,
) -> str | InputRequiredResult:
    """Buy a pet. The shop asks the customer for a pickup slot before completing."""
    pv = ctx.request_context.protocol_version if ctx.request_context else None
    can = client_can_elicit(ctx)
    log(f"buy_pet pet_id={pet_id} pv={pv} elicitation_cap={can} "
        f"input_responses={ctx.input_responses!r} pickup_slot={pickup_slot!r}")

    # Fallback path / explicit parameter
    if pickup_slot is not None:
        if pickup_slot not in SLOTS:
            raise ToolError(f"Unknown pickup slot {pickup_slot!r}. Offered: {list(SLOTS)}")
        return complete(pet_id, pickup_slot)

    if not can:
        offered = "; ".join(f"{v} ({t})" for v, t in SLOTS.items())
        raise ToolError(
            f"Pick a pickup slot: {offered}. Then call buy_pet with pickup_slot=<slot>."
        )

    if pv in MODERN_PROTOCOL_VERSIONS:
        # 2026-07-28: stateless multi round-trip
        responses = ctx.input_responses
        if not responses or "pickup" not in responses:
            return InputRequiredResult(
                input_requests={
                    "pickup": ElicitRequest(
                        params=ElicitRequestFormParams(
                            message=PICKUP_MESSAGE, requested_schema=pickup_schema()
                        )
                    )
                },
                request_state=json.dumps({"pet_id": pet_id, "reservation_id": reservation_id}),
            )
        log("request_state echoed:", ctx.request_state)
        answer = responses["pickup"]
        action, content = answer.action, answer.content
    else:
        # handshake era: server-initiated elicitation/create
        r = await ctx.elicit(
            PICKUP_MESSAGE,
            response_type={v: {"title": t} for v, t in SLOTS.items()},
            response_title="Pickup slot",
        )
        action = r.action
        content = {"pickup_slot": r.data} if action == "accept" else None

    if action == "decline":
        return "Purchase not completed: the customer declined to pick a pickup slot."
    if action == "cancel":
        return "Purchase cancelled by the customer."
    slot = (content or {}).get("pickup_slot")
    if slot not in SLOTS:
        raise ToolError(f"Invalid pickup slot {slot!r}")
    return complete(pet_id, slot)


# ---------------------------------------------------------------- wire logger
WIRE_LOG = Path(__file__).with_name("wire.jsonl")


class WireLogger:
    """ASGI middleware: append every HTTP request/response body to wire.jsonl."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        rid = f"{time.time():.6f}"
        hdrs = {k.decode(): v.decode() for k, v in scope["headers"]
                if k.decode().lower().startswith(("mcp", "accept", "content-type", "user-agent"))}

        async def recv():
            msg = await receive()
            if msg["type"] == "http.request" and msg.get("body"):
                self._w(rid, "request", scope["method"], hdrs, msg["body"])
            return msg

        async def snd(msg):
            if msg["type"] == "http.response.start":
                self._w(rid, "response.start", msg["status"],
                        {k.decode(): v.decode() for k, v in msg.get("headers", [])
                         if k.decode().lower().startswith(("mcp", "content-type"))}, b"")
            elif msg["type"] == "http.response.body" and msg.get("body"):
                self._w(rid, "response", None, None, msg["body"])
            await send(msg)

        await self.app(scope, recv, snd)

    @staticmethod
    def _w(rid, kind, a, hdrs, body: bytes):
        text = body.decode(errors="replace")
        entry = {"t": rid, "kind": kind, "info": a, "headers": hdrs, "body": text}
        with WIRE_LOG.open("a") as f:
            f.write(json.dumps(entry) + "\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "stdio":
        mcp.run(transport="stdio")
    else:
        import uvicorn

        port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
        uvicorn.run(WireLogger(mcp.http_app(path="/mcp")), host="127.0.0.1", port=port,
                    log_level="warning")
