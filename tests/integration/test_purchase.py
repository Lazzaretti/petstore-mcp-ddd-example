"""A full purchase across the contexts, over real Streamable HTTP on the three endpoints."""

import httpx2
import pytest
from fastmcp import Client

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def test_find_buy_schedule_and_see_it_in_my_purchases(app_url: str) -> None:
    async with (
        Client(f"{app_url}/discovery/mcp") as discovery,
        Client(f"{app_url}/sales/mcp") as sales,
        Client(f"{app_url}/handover/mcp") as handover,
    ):
        found = await discovery.call_tool("find_available_pets", {"species": "dog", "tag": "friendly"})
        assert [p["name"] for p in found.structured_content["result"]] == ["Rex", "Bello"]

        bought = (await sales.call_tool("buy_pet", {"pet_id": 1})).structured_content
        slot = bought["free_slots"][0]["value"]
        scheduled = await sales.call_tool(
            "schedule_pickup", {"purchase_id": bought["purchase_id"], "pickup_slot": slot}
        )
        assert scheduled.structured_content["pickup"]["value"] == slot

        # The events arrived: Pet Discovery took Rex off offer, Pet Handover has the purchase with the slot.
        found = await discovery.call_tool("find_available_pets", {"species": "dog", "tag": "friendly"})
        assert [p["name"] for p in found.structured_content["result"]] == ["Bello"]
        mine = (await handover.call_tool("my_purchases", {})).structured_content["result"]
        assert mine == [
            {"purchase_id": bought["purchase_id"], "pet": "Rex", "pickup": scheduled.structured_content["pickup"]}
        ]

        refused = await sales.call_tool("buy_pet", {"pet_id": 1}, raise_on_error=False)
        assert refused.is_error and refused.content[0].text.startswith("PetNotAvailable: Rex is already sold.")

    stock = httpx2.get(f"{app_url}/sales/stock").json()
    assert stock == {"available": 2, "reserved": 0, "sold": 2}
