"""`app.py demo`: the scripted run. No model, AUTH=off, the customer per scene, a settable clock.

Scenes 1-5 are the recording for the talk (`--until 5`); 6-8 show the remaining rules.
"""

import json
import logging
import os
import sys
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any, TextIO
from zoneinfo import ZoneInfo

from fastmcp import Client

from petstore.app import create_petstore, create_servers
from petstore.sales import sequential_ids

# The talk: Mon, Nov 9, 2026, 4:45 PM in Denver.
TALK = datetime(2026, 11, 9, 16, 45, tzinfo=ZoneInfo("America/Denver"))


def format_result(result: dict[str, Any]) -> str:
    """One line per field (or per list item), compact JSON values: readable on a slide."""
    if list(result) == ["result"]:
        lines = [json.dumps(item, ensure_ascii=False) for item in result["result"]] or ["[]"]
    else:
        lines = [f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in result.items()]
    return "← " + "\n  ".join(lines)


class Stage:
    """Prints each scene, each call and its result."""

    def __init__(self, clients: dict[str, Client], until: int, pause: bool, out: TextIO) -> None:
        self._clients = clients
        self._until = until
        self._pause = pause
        self._out = out

    def scene(self, number: int, customer: str, title: str) -> bool:
        """Starts a scene as `customer`; False once past the last scene to show."""
        if number > 1 and self._pause:
            input("  (Enter for the next scene)")
        if number > self._until:
            return False
        os.environ["PETSTORE_CUSTOMER"] = customer
        self._print(f"\n━━ Scene {number} · {customer} · {title} ━━")
        return True

    def note(self, text: str) -> None:
        self._print(f"   {text}")

    async def call(self, context: str, tool: str, **arguments: Any) -> dict[str, Any] | None:
        self._print(f"→ petstore-{context}  {tool} {json.dumps(arguments)}")
        result = await self._clients[context].call_tool(tool, arguments, raise_on_error=False)
        if result.is_error:
            self._print(f"← isError: {result.content[0].text}")
            return None
        self._print(format_result(result.structured_content))
        return result.structured_content

    def _print(self, text: str) -> None:
        print(text, file=self._out)


async def run(until: int = 8, pause: bool = False, out: TextIO = sys.stdout) -> None:
    os.environ["AUTH"] = "off"
    logging.getLogger("fastmcp").setLevel(logging.WARNING)  # refusals are part of the show, not log lines
    now = None if os.environ.get("PETSTORE_NOW") else TALK
    petstore = create_petstore(now=now, new_id=sequential_ids())
    servers = create_servers(petstore)
    async with (
        Client(servers["discovery"]) as discovery,
        Client(servers["sales"]) as sales,
        Client(servers["handover"]) as handover,
    ):
        stage = Stage({"discovery": discovery, "sales": sales, "handover": handover}, until, pause, out)
        stage.note(f"Shop time: {petstore.clock.now():%a, %b %d, %Y %H:%M} (America/Denver)")
        await _play(stage, petstore.clock.advance)


async def _play(stage: Stage, advance_clock: Callable[[timedelta], None]) -> None:
    if not stage.scene(1, "alice", "Buy me a friendly dog: what's on offer?"):
        return
    await stage.call("discovery", "find_available_pets", species="dog", tag="friendly")

    if not stage.scene(2, "alice", "buy Rex without a pickup slot"):
        return
    purchase = await stage.call("sales", "buy_pet", pet_id=1)
    assert purchase is not None
    purchase_id = purchase["purchase_id"]

    if not stage.scene(3, "alice", "she picks the first free slot"):
        return
    first_free_slot = purchase["free_slots"][0]["value"]
    await stage.call("sales", "schedule_pickup", purchase_id=purchase_id, pickup_slot=first_free_slot)

    if not stage.scene(4, "bob", "Bob wants Rex too"):
        return
    await stage.call("sales", "buy_pet", pet_id=1)

    if not stage.scene(5, "alice", "Pet Handover got the events"):
        return
    await stage.call("handover", "my_purchases")

    if not stage.scene(6, "alice", "a reservation runs out"):
        return
    reservation = await stage.call("sales", "reserve_pet", pet_id=3)
    assert reservation is not None
    advance_clock(timedelta(hours=25))
    stage.note("⏩ clock + 25 h")
    await stage.call("sales", "buy_pet", pet_id=3, reservation_id=reservation["reservation_id"])
    await stage.call("discovery", "find_available_pets", species="dog")

    if not stage.scene(7, "alice", "move the pickup, then cancel, after the slot"):
        return
    await stage.call("sales", "schedule_pickup", purchase_id=purchase_id, pickup_slot="2026-11-12T10:00")
    await stage.call("sales", "cancel_purchase", purchase_id=purchase_id)

    if not stage.scene(8, "bob", "Bob tries to cancel Alice's purchase"):
        return
    await stage.call("sales", "cancel_purchase", purchase_id=purchase_id)
