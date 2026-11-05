import httpx2
import pytest
from fastmcp import Client
from fastmcp.client.auth import BearerAuth

from tests.integration.keycloak_login import access_token

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def test_a_sales_token_works_on_pet_sales(app_with_auth: str) -> None:
    token = access_token("alice", "sales")
    async with Client(f"{app_with_auth}/sales/mcp", auth=BearerAuth(token)) as client:
        assert client.server_info.name == "petstore-sales"


def test_a_sales_token_is_rejected_by_pet_discovery(app_with_auth: str) -> None:
    token = access_token("alice", "sales")
    response = httpx2.post(
        f"{app_with_auth}/discovery/mcp",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json, text/event-stream"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    assert response.status_code in (401, 403)


def test_without_a_token_the_server_points_to_its_protected_resource_metadata(app_with_auth: str) -> None:
    request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    response = httpx2.post(f"{app_with_auth}/sales/mcp", json=request)
    assert response.status_code == 401
    assert "/.well-known/oauth-protected-resource/sales/mcp" in response.headers["www-authenticate"]


def client_for(app_url: str, user: str, context: str) -> Client:
    return Client(f"{app_url}/{context}/mcp", auth=BearerAuth(access_token(user, context)))


async def test_the_customer_comes_from_the_token(app_with_auth: str) -> None:
    async with client_for(app_with_auth, "alice", "sales") as sales:
        bought = (await sales.call_tool("buy_pet", {"pet_id": 2})).structured_content
    async with client_for(app_with_auth, "alice", "handover") as handover:
        mine = (await handover.call_tool("my_purchases", {})).structured_content["result"]
    assert bought["purchase_id"] in [p["purchase_id"] for p in mine]

    async with client_for(app_with_auth, "bob", "handover") as handover:
        assert (await handover.call_tool("my_purchases", {})).structured_content["result"] == []
    async with client_for(app_with_auth, "bob", "sales") as sales:
        refused = await sales.call_tool("cancel_purchase", {"purchase_id": bought["purchase_id"]}, raise_on_error=False)
    assert refused.is_error
    assert refused.content[0].text.startswith("UnknownPurchase:")


async def test_a_discovery_token_works_on_pet_discovery(app_with_auth: str) -> None:
    async with client_for(app_with_auth, "bob", "discovery") as discovery:
        assert [t.name for t in await discovery.list_tools()] == ["find_available_pets"]


def test_each_server_publishes_its_protected_resource_metadata(app_with_auth: str) -> None:
    for context in ("discovery", "sales", "handover"):
        metadata = httpx2.get(f"{app_with_auth}/.well-known/oauth-protected-resource/{context}/mcp").json()
        assert metadata["resource"] == f"http://localhost:8000/{context}/mcp"
        assert metadata["authorization_servers"] == ["http://localhost:8080/realms/petstore"]
