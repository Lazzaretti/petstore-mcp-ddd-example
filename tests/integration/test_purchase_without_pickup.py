"""PICKUP=off over real Streamable HTTP: buy, see it in Pet Handover, no pickup anywhere."""

from collections.abc import Iterator

import pytest
from fastmcp import Client

from tests.integration.conftest import free_port, running_app

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


@pytest.fixture(scope="module")
def app_without_pickup() -> Iterator[str]:
    with running_app(free_port(), AUTH="off", PETSTORE_CUSTOMER="alice", PICKUP="off") as url:
        yield url


async def test_find_buy_and_see_it_in_my_purchases_without_pickup(app_without_pickup: str) -> None:
    async with (
        Client(f"{app_without_pickup}/discovery/mcp") as discovery,
        Client(f"{app_without_pickup}/sales/mcp") as sales,
        Client(f"{app_without_pickup}/handover/mcp") as handover,
    ):
        assert [t.name for t in await sales.list_tools()] == ["reserve_pet", "buy_pet", "cancel_purchase"]
        bought = (await sales.call_tool("buy_pet", {"pet_id": 3})).structured_content
        assert "pickup" not in bought and "free_slots" not in bought
        found = (await discovery.call_tool("find_available_pets", {"species": "dog"})).structured_content
        assert [p["name"] for p in found["result"]] == ["Rex"]
        mine = (await handover.call_tool("my_purchases", {})).structured_content["result"]
        assert mine == [{"purchase_id": bought["purchase_id"], "pet": "Bello"}]
