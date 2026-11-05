"""What happened in one take of the after clip, from Claude Code's session transcript and the app.

Per prompt: the tool calls (name, arguments, error text) and the agent's last words. Then the final
state, asked from the running app as alice (AUTH=off): her purchases with their pickup slots, what is
still on offer, and the stock counts. Expected: Rex sold to alice with a pickup slot, no second purchase.
Usage: uv run python scripts/check_after_take.py --out take.json
"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import httpx2
from check_before_take import latest_session, turns
from fastmcp import Client

import eval as evaluation

STAGE = evaluation.ROOT / "stage-after"
APP = f"http://localhost:{evaluation.AFTER_PORT}"


async def call(context: str, tool: str) -> Any:
    async with Client(f"{APP}/{context}/mcp") as client:
        return (await client.call_tool(tool, {})).structured_content["result"]


def final_state() -> dict[str, Any]:
    purchases = asyncio.run(call("handover", "my_purchases"))
    on_offer = [pet["name"] for pet in asyncio.run(call("discovery", "find_available_pets"))]
    rex = [p for p in purchases if p["pet"] == "Rex"]
    return {
        "alices_purchases": purchases,
        "on_offer": on_offer,
        "stock": httpx2.get(f"{APP}/sales/stock", timeout=10).json(),
        "rex_sold_to_alice": len(rex) == 1,
        "pickup_slot": rex[0]["pickup"]["title"] if rex and rex[0].get("pickup") else None,
        "second_purchase": len(purchases) > 1,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()
    session = latest_session(STAGE)
    report = {"session": session.name, "turns": turns(session), "final_state": final_state()}
    arguments.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    for number, turn in enumerate(report["turns"], start=1):
        chain = " → ".join(c["tool"] + (" (error)" if c["error"] else "") for c in turn["calls"]) or "(no calls)"
        print(f"({number}) {turn['prompt']}\n    {chain}\n    {turn['answer'][:300]!r}")
        for c in turn["calls"]:
            if c.get("error_text"):
                print(f"    {c['tool']} error: {c['error_text']}")
    state = report["final_state"]
    print(
        f"Rex sold to alice: {state['rex_sold_to_alice']}, pickup: {state['pickup_slot']}, "
        f"second purchase: {state['second_purchase']}, on offer: {', '.join(state['on_offer'])}"
    )


if __name__ == "__main__":
    main()
