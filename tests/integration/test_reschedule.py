"""Review finding: move a passed pickup to the future, then cancel. Over real Streamable HTTP.

The app runs in this process (uvicorn on a free port) so the test can move the shop clock;
a separate process has a fixed PETSTORE_NOW, and a pickup slot is always at least a day ahead.
"""

import threading
import time
from collections.abc import Iterator
from datetime import timedelta

import pytest
import uvicorn
from fastmcp import Client

from petstore.app import Petstore, create_app, create_petstore
from tests.factories import TALK
from tests.integration.conftest import free_port

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


@pytest.fixture(scope="module")
def petstore() -> Petstore:
    return create_petstore(now=TALK, pickup=True)


@pytest.fixture(scope="module")
def app_url(petstore: Petstore) -> Iterator[str]:
    with pytest.MonkeyPatch.context() as env:
        env.setenv("AUTH", "off")
        env.setenv("PETSTORE_CUSTOMER", "alice")
        port = free_port()
        app = create_app(petstore)
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        while not server.started:
            time.sleep(0.05)
        yield f"http://localhost:{port}"
        server.should_exit = True
        thread.join(timeout=10)


async def test_a_passed_pickup_can_be_neither_moved_nor_cancelled(app_url: str, petstore: Petstore) -> None:
    async with Client(f"{app_url}/sales/mcp") as sales, Client(f"{app_url}/handover/mcp") as handover:
        bought = (await sales.call_tool("buy_pet", {"pet_id": 1, "pickup_slot": "2026-11-10T10:00"})).structured_content
        petstore.clock.advance(timedelta(days=1))  # Tue, Nov 10, 4:45 PM: the slot has passed

        moved = await sales.call_tool(
            "schedule_pickup",
            {"purchase_id": bought["purchase_id"], "pickup_slot": "2026-11-12T10:00"},
            raise_on_error=False,
        )
        assert moved.is_error and moved.content[0].text.startswith("TooLateToReschedule: Rex was due for pickup")

        cancelled = await sales.call_tool(
            "cancel_purchase", {"purchase_id": bought["purchase_id"]}, raise_on_error=False
        )
        assert cancelled.is_error and cancelled.content[0].text.startswith("TooLateToCancel: Rex was due for pickup")

        [mine] = (await handover.call_tool("my_purchases", {})).structured_content["result"]
        assert mine["pickup"]["value"] == "2026-11-10T10:00"
