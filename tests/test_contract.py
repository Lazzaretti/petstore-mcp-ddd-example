"""Contract tests: what the agent sees and gets back, through MCP (FastMCP's in-memory Client)."""

from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

import httpx2
import pytest
from fastmcp import Client, FastMCP

from petstore.app import Petstore, create_app, create_petstore, create_servers
from tests.factories import TALK

pytestmark = pytest.mark.anyio

TOOLS = {
    "discovery": ["find_available_pets"],
    "sales": ["reserve_pet", "buy_pet", "schedule_pickup", "cancel_purchase"],
    "handover": ["my_purchases"],
}
ANNOTATIONS = {
    "find_available_pets": {"readOnlyHint": True, "idempotentHint": True},
    "my_purchases": {"readOnlyHint": True, "idempotentHint": True},
    "reserve_pet": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True},
    "buy_pet": {"readOnlyHint": False, "destructiveHint": False},
    "schedule_pickup": {"readOnlyHint": False, "destructiveHint": False},
    "cancel_purchase": {"readOnlyHint": False, "destructiveHint": True},
}
PARAMETERS = {
    "find_available_pets": ([], ["species", "tag"]),
    "reserve_pet": (["pet_id"], ["pet_id"]),
    "buy_pet": (["pet_id"], ["pet_id", "pickup_slot", "reservation_id"]),
    "schedule_pickup": (["purchase_id", "pickup_slot"], ["purchase_id", "pickup_slot"]),
    "cancel_purchase": (["purchase_id"], ["purchase_id"]),
    "my_purchases": ([], []),
}
SLOT_KEYS = {"value", "title"}


@pytest.fixture
def petstore() -> Petstore:
    return create_petstore(now=TALK)


@pytest.fixture
async def clients(petstore: Petstore) -> AsyncIterator[dict[str, Client]]:
    servers: dict[str, FastMCP] = create_servers(petstore)
    async with (
        Client(servers["discovery"]) as discovery,
        Client(servers["sales"]) as sales,
        Client(servers["handover"]) as handover,
    ):
        yield {"discovery": discovery, "sales": sales, "handover": handover}


async def call(client: Client, tool: str, **arguments: Any) -> Any:
    result = await client.call_tool(tool, arguments)
    return result.structured_content


async def refusal(client: Client, tool: str, **arguments: Any) -> str:
    result = await client.call_tool(tool, arguments, raise_on_error=False)
    assert result.is_error
    return result.content[0].text


# --- the tool list -------------------------------------------------------------------------------------


@pytest.mark.parametrize("context", TOOLS)
async def test_each_server_offers_only_its_contexts_tools(clients: dict[str, Client], context: str) -> None:
    assert [tool.name for tool in await clients[context].list_tools()] == TOOLS[context]


async def test_annotations_follow_the_table(clients: dict[str, Client]) -> None:
    for client in clients.values():
        for tool in await client.list_tools():
            annotations = tool.annotations.model_dump(by_alias=True, exclude_none=True)
            assert annotations == ANNOTATIONS[tool.name], tool.name


async def test_every_tool_has_a_title_a_description_and_an_output_schema(clients: dict[str, Client]) -> None:
    for client in clients.values():
        for tool in await client.list_tools():
            assert tool.title and tool.description and tool.output_schema, tool.name


async def test_parameters_never_include_the_customer(clients: dict[str, Client]) -> None:
    for client in clients.values():
        for tool in await client.list_tools():
            required, properties = PARAMETERS[tool.name]
            assert tool.input_schema.get("required", []) == required, tool.name
            assert list(tool.input_schema.get("properties", {})) == properties, tool.name


async def test_pet_ids_are_integers(clients: dict[str, Client]) -> None:
    [buy_pet] = [t for t in await clients["sales"].list_tools() if t.name == "buy_pet"]
    assert buy_pet.input_schema["properties"]["pet_id"]["type"] == "integer"


async def test_the_reservation_tool_describes_the_configured_hold(clients: dict[str, Client]) -> None:
    [reserve_pet] = [t for t in await clients["sales"].list_tools() if t.name == "reserve_pet"]
    assert "24 hours" in reserve_pet.description


# --- results ---------------------------------------------------------------------------------------------


async def test_find_available_pets_answers_in_domain_words(clients: dict[str, Client]) -> None:
    result = await call(clients["discovery"], "find_available_pets", species="dog", tag="friendly")
    assert result == {
        "result": [
            {"pet_id": 1, "name": "Rex", "species": "dog", "tags": ["friendly"]},
            {"pet_id": 3, "name": "Bello", "species": "dog", "tags": ["puppy", "friendly"]},
        ]
    }


async def test_buying_without_a_slot_lists_free_slots_and_the_next_step(clients: dict[str, Client]) -> None:
    result = await call(clients["sales"], "buy_pet", pet_id=1)
    assert result["purchase_id"].startswith("pur-")
    assert (result["pet_id"], result["pet"], result["pickup"]) == (1, "Rex", None)
    assert len(result["free_slots"]) == 6
    assert result["free_slots"][0] == {"value": "2026-11-10T10:00", "title": "Tue, Nov 10, 10:00 AM"}
    assert result["next_step"].startswith(
        "Rex is yours. Pickup not scheduled yet. Free slots: Tue, Nov 10, 10:00 AM (2026-11-10T10:00), "
    )
    assert result["next_step"].endswith("Ask the customer, then call schedule_pickup.")


async def test_buying_with_a_slot_has_no_free_slots(clients: dict[str, Client]) -> None:
    result = await call(clients["sales"], "buy_pet", pet_id=1, pickup_slot="2026-11-10T10:00")
    assert result["pickup"] == {"value": "2026-11-10T10:00", "title": "Tue, Nov 10, 10:00 AM"}
    assert "free_slots" not in result
    assert result["next_step"] == "Rex is yours. Pickup at the shop on Tue, Nov 10, 10:00 AM."


async def test_scheduling_the_pickup(clients: dict[str, Client]) -> None:
    purchase = await call(clients["sales"], "buy_pet", pet_id=1)
    result = await call(
        clients["sales"], "schedule_pickup", purchase_id=purchase["purchase_id"], pickup_slot="2026-11-10T10:00"
    )
    assert result == {
        "purchase_id": purchase["purchase_id"],
        "pet": "Rex",
        "pickup": {"value": "2026-11-10T10:00", "title": "Tue, Nov 10, 10:00 AM"},
        "next_step": "Pickup scheduled: Rex at the shop on Tue, Nov 10, 10:00 AM. Free to cancel until then.",
    }


async def test_reserving_returns_the_reservation_and_how_long_it_holds(clients: dict[str, Client]) -> None:
    result = await call(clients["sales"], "reserve_pet", pet_id=1)
    assert result["reservation_id"].startswith("res-")
    assert result["expires"] == {"value": "2026-11-10T16:45", "title": "Tue, Nov 10, 4:45 PM"}
    assert result["next_step"] == (
        "Rex is reserved for you until Tue, Nov 10, 4:45 PM. To buy, call buy_pet with pet_id 1."
    )


async def test_reserving_again_says_it_is_already_reserved(clients: dict[str, Client]) -> None:
    first = await call(clients["sales"], "reserve_pet", pet_id=1)
    again = await call(clients["sales"], "reserve_pet", pet_id=1)
    assert again["reservation_id"] == first["reservation_id"]
    assert again["next_step"].startswith("Rex is already reserved for you until Tue, Nov 10, 4:45 PM.")


async def test_cancelling(clients: dict[str, Client]) -> None:
    purchase = await call(clients["sales"], "buy_pet", pet_id=1)
    result = await call(clients["sales"], "cancel_purchase", purchase_id=purchase["purchase_id"])
    assert result == {
        "purchase_id": purchase["purchase_id"],
        "pet": "Rex",
        "status": "cancelled",
        "next_step": "Purchase cancelled; Rex is back on offer.",
    }


async def test_my_purchases_shows_active_purchases_with_slots(clients: dict[str, Client]) -> None:
    purchase = await call(clients["sales"], "buy_pet", pet_id=1, pickup_slot="2026-11-10T10:00")
    cancelled = await call(clients["sales"], "buy_pet", pet_id=2)
    await call(clients["sales"], "cancel_purchase", purchase_id=cancelled["purchase_id"])
    assert await call(clients["handover"], "my_purchases") == {
        "result": [
            {
                "purchase_id": purchase["purchase_id"],
                "pet": "Rex",
                "pickup": {"value": "2026-11-10T10:00", "title": "Tue, Nov 10, 10:00 AM"},
            }
        ]
    }


# --- errors: isError, a text starting with the error name ---------------------------------------------


async def test_a_sold_pet_is_refused(clients: dict[str, Client]) -> None:
    text = await refusal(clients["sales"], "buy_pet", pet_id=4)
    assert text == "PetNotAvailable: Max is already sold. Use find_available_pets for others."


async def test_an_unknown_pet_is_refused(clients: dict[str, Client]) -> None:
    text = await refusal(clients["sales"], "reserve_pet", pet_id=7)
    assert text == "UnknownPet: No pet with id 7. Use find_available_pets to get ids."


async def test_a_taken_slot_is_refused_with_free_slots(clients: dict[str, Client]) -> None:
    await call(clients["sales"], "buy_pet", pet_id=1, pickup_slot="2026-11-10T10:00")
    purchase = await call(clients["sales"], "buy_pet", pet_id=3)
    text = await refusal(
        clients["sales"], "schedule_pickup", purchase_id=purchase["purchase_id"], pickup_slot="2026-11-10T10:00"
    )
    assert text.startswith("SlotNotAvailable: Tue, Nov 10, 10:00 AM was just taken. Free slots: Tue, Nov 10, 11:00 AM")
    assert text.endswith("Call schedule_pickup with one of them.")


async def test_too_late_to_cancel(clients: dict[str, Client], petstore: Petstore) -> None:
    purchase = await call(clients["sales"], "buy_pet", pet_id=1, pickup_slot="2026-11-10T10:00")
    petstore.clock.advance(timedelta(days=1))
    text = await refusal(clients["sales"], "cancel_purchase", purchase_id=purchase["purchase_id"])
    assert text.startswith("TooLateToCancel: Rex was due for pickup on Tue, Nov 10, 10:00 AM.")


async def test_too_late_to_move_the_pickup(clients: dict[str, Client], petstore: Petstore) -> None:
    purchase = await call(clients["sales"], "buy_pet", pet_id=1, pickup_slot="2026-11-10T10:00")
    petstore.clock.advance(timedelta(days=1))
    text = await refusal(
        clients["sales"], "schedule_pickup", purchase_id=purchase["purchase_id"], pickup_slot="2026-11-12T10:00"
    )
    assert text == (
        "TooLateToReschedule: Rex was due for pickup on Tue, Nov 10, 10:00 AM. "
        "Too late to move the pickup; contact the shop."
    )


async def test_an_expired_reservation_is_refused(clients: dict[str, Client], petstore: Petstore) -> None:
    reservation = await call(clients["sales"], "reserve_pet", pet_id=3)
    petstore.clock.advance(timedelta(hours=25))
    text = await refusal(clients["sales"], "buy_pet", pet_id=3, reservation_id=reservation["reservation_id"])
    assert text.startswith("ReservationExpired: Bello's reservation ran out.")


# --- customer isolation ---------------------------------------------------------------------------


async def test_customers_never_see_each_others_purchases(
    clients: dict[str, Client], monkeypatch: pytest.MonkeyPatch
) -> None:
    purchase = await call(clients["sales"], "buy_pet", pet_id=1)
    monkeypatch.setenv("PETSTORE_CUSTOMER", "bob")
    assert await call(clients["handover"], "my_purchases") == {"result": []}
    for tool, arguments in (
        ("cancel_purchase", {}),
        ("schedule_pickup", {"pickup_slot": "2026-11-10T10:00"}),
    ):
        text = await refusal(clients["sales"], tool, purchase_id=purchase["purchase_id"], **arguments)
        assert text == f"UnknownPurchase: No purchase with id {purchase['purchase_id']}. Use my_purchases to see yours."


async def test_a_pet_reserved_by_alice_is_refused_to_bob(
    clients: dict[str, Client], monkeypatch: pytest.MonkeyPatch
) -> None:
    await call(clients["sales"], "reserve_pet", pet_id=1)
    monkeypatch.setenv("PETSTORE_CUSTOMER", "bob")
    text = await refusal(clients["sales"], "reserve_pet", pet_id=1)
    assert text.startswith("PetNotAvailable: Rex is reserved by someone else.")


# --- policies and stock --------------------------------------------------------------------------------


async def test_the_policies_resource(clients: dict[str, Client]) -> None:
    [resource] = await clients["sales"].list_resources()
    assert (str(resource.uri), resource.mime_type) == ("pet-sales://policies", "text/markdown")
    [contents] = await clients["sales"].read_resource("pet-sales://policies")
    assert "holds the pet for 24 hours" in contents.text


async def test_only_pet_sales_has_a_resource(clients: dict[str, Client]) -> None:
    assert await clients["discovery"].list_resources() == []
    assert await clients["handover"].list_resources() == []


async def test_the_stock_is_rest_not_a_tool(petstore: Petstore) -> None:
    transport = httpx2.ASGITransport(app=create_app(petstore))
    async with httpx2.AsyncClient(transport=transport, base_url="http://localhost") as http:
        response = await http.get("/sales/stock")
    assert response.json() == {"available": 3, "reserved": 0, "sold": 1}
