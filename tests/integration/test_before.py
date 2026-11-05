"""The before server against the local Petstore: same pets, no rules."""

import pytest
from fastmcp import Client

import petstore_before

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def test_the_before_side_sees_the_same_pets(local_petstore: str) -> None:
    async with Client(petstore_before.create_server(local_petstore)) as client:
        found = await client.call_tool("findPetsByTags", {"tags": ["friendly"]})
    assert {(p["name"], p["status"]) for p in found.structured_content["result"]} == {
        ("Rex", "available"),
        ("Bello", "available"),
        ("Max", "sold"),
    }


async def test_a_sold_pet_can_be_ordered(local_petstore: str) -> None:
    async with Client(petstore_before.create_server(local_petstore)) as client:
        order = await client.call_tool("placeOrder", {"petId": 4, "quantity": 1, "status": "placed"})
    assert not order.is_error
    assert order.structured_content["petId"] == 4


async def test_an_unknown_pet_is_an_http_error(local_petstore: str) -> None:
    async with Client(petstore_before.create_server(local_petstore)) as client:
        result = await client.call_tool("getPetById", {"petId": 7}, raise_on_error=False)
    assert result.is_error and "404" in result.content[0].text
