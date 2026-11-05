import pytest
from fastmcp import Client

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


@pytest.mark.parametrize("context", ["discovery", "sales", "handover"])
async def test_each_endpoint_answers_over_streamable_http(app_url: str, context: str) -> None:
    async with Client(f"{app_url}/{context}/mcp") as client:
        assert client.server_info.name == f"petstore-{context}"
