import asyncio
from datetime import timedelta

import pytest
from fastmcp import Client
from starlette.applications import Starlette

from petstore import app
from tests.factories import TALK

pytestmark = pytest.mark.anyio

SERVER_IDS = {"discovery": "petstore-discovery", "sales": "petstore-sales", "handover": "petstore-handover"}


def test_the_app_serves_one_streamable_http_endpoint_per_context() -> None:
    paths = {route.path for route in app.create_app().routes}
    assert {"/discovery", "/sales", "/handover"} <= paths


@pytest.mark.parametrize("context", SERVER_IDS)
async def test_each_server_has_its_id_and_a_one_sentence_instruction(context: str) -> None:
    server = app.create_servers()[context]
    async with Client(server) as client:
        assert client.server_info.name == SERVER_IDS[context]
        instructions = client.instructions or ""
        assert instructions.endswith(".")
        assert instructions.count(". ") == 0


async def test_the_sweeper_expires_reservations_without_a_call() -> None:
    petstore = app.create_petstore(now=TALK)
    petstore.sales.reserve_pet("alice", 3)
    petstore.clock.advance(timedelta(hours=25))
    async with app.reservation_sweeper(petstore.sales, every=0.01)(Starlette()):
        await asyncio.sleep(0.05)
    assert "Bello" in [o.name for o in petstore.discovery.find_available_pets()]
