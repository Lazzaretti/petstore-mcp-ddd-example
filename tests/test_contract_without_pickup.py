"""Contract tests with PICKUP=off: the after side with the original Petstore API's scope."""

import json
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
from fastmcp import Client

from petstore.app import Petstore, create_petstore, create_servers
from tests.factories import TALK

pytestmark = pytest.mark.anyio


@pytest.fixture
def petstore() -> Petstore:
    return create_petstore(now=TALK, pickup=False)


@pytest.fixture
async def clients(petstore: Petstore) -> AsyncIterator[dict[str, Client]]:
    servers = create_servers(petstore)
    async with Client(servers["sales"]) as sales, Client(servers["handover"]) as handover:
        yield {"sales": sales, "handover": handover}


async def tools_by_name(client: Client) -> dict:
    return {tool.name: tool for tool in await client.list_tools()}


async def test_pet_sales_has_no_schedule_pickup(clients: dict[str, Client]) -> None:
    assert list(await tools_by_name(clients["sales"])) == ["reserve_pet", "buy_pet", "cancel_purchase"]


async def test_buy_pet_has_no_pickup_slot_and_no_pickup_in_its_output_schema(clients: dict[str, Client]) -> None:
    buy_pet = (await tools_by_name(clients["sales"]))["buy_pet"]
    assert list(buy_pet.input_schema["properties"]) == ["pet_id", "reservation_id"]
    assert set(buy_pet.output_schema["properties"]) == {"purchase_id", "pet_id", "pet", "next_step"}
    assert "pickup" not in (buy_pet.description or "").lower()


async def test_no_tool_or_instruction_mentions_the_pickup(clients: dict[str, Client]) -> None:
    for client in clients.values():
        assert "pickup" not in (client.instructions or "").lower()
        for tool in await client.list_tools():
            assert "pickup" not in tool.model_dump_json().lower(), tool.name


async def test_buying_returns_no_pickup_and_no_free_slots(clients: dict[str, Client]) -> None:
    result = (await clients["sales"].call_tool("buy_pet", {"pet_id": 1})).structured_content
    assert set(result) == {"purchase_id", "pet_id", "pet", "next_step"}
    assert result["next_step"] == "Rex is yours."


async def test_my_purchases_works_without_pickup(clients: dict[str, Client]) -> None:
    bought = (await clients["sales"].call_tool("buy_pet", {"pet_id": 1})).structured_content
    my_purchases = (await tools_by_name(clients["handover"]))["my_purchases"]
    assert "pickup" not in json_text(my_purchases.output_schema)
    result = await clients["handover"].call_tool("my_purchases", {})
    assert result.structured_content == {"result": [{"purchase_id": bought["purchase_id"], "pet": "Rex"}]}


async def test_cancelling_is_allowed_any_time(clients: dict[str, Client], petstore: Petstore) -> None:
    bought = (await clients["sales"].call_tool("buy_pet", {"pet_id": 1})).structured_content
    petstore.clock.advance(timedelta(days=30))
    result = await clients["sales"].call_tool("cancel_purchase", {"purchase_id": bought["purchase_id"]})
    assert result.structured_content["status"] == "cancelled"


async def test_the_policies_have_no_pickup_lines(clients: dict[str, Client]) -> None:
    [contents] = await clients["sales"].read_resource("pet-sales://policies")
    assert "pickup" not in contents.text.lower()


def json_text(schema: dict) -> str:
    return json.dumps(schema).lower()


def test_the_switch_is_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PICKUP", "off")
    assert create_petstore(now=TALK).pickup is False
    monkeypatch.setenv("PICKUP", "on")
    assert create_petstore(now=TALK).pickup is True
    monkeypatch.delenv("PICKUP")
    assert create_petstore(now=TALK).pickup is True
    monkeypatch.setenv("PICKUP", "maybe")
    with pytest.raises(ValueError, match="PICKUP"):
        create_petstore(now=TALK)
