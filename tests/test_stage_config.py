"""The stage host config: three servers, read tools pre-allowed, every write asks the host."""

import json
from pathlib import Path

import pytest
from fastmcp import Client

from petstore.app import create_servers

pytestmark = pytest.mark.anyio

STAGE = Path(__file__).resolve().parents[1] / "stage"


async def tool_permissions() -> dict[str, bool]:
    """mcp__<server>__<tool> -> readOnlyHint, from the servers themselves."""
    permissions = {}
    for server in create_servers().values():
        async with Client(server) as client:
            for tool in await client.list_tools():
                permissions[f"mcp__{server.name}__{tool.name}"] = bool(tool.annotations.read_only_hint)
    return permissions


def test_the_host_config_points_at_the_three_endpoints() -> None:
    servers = json.loads((STAGE / ".mcp.json").read_text())["mcpServers"]
    assert {name: s["url"] for name, s in servers.items()} == {
        "petstore-discovery": "http://localhost:8000/discovery/mcp",
        "petstore-sales": "http://localhost:8000/sales/mcp",
        "petstore-handover": "http://localhost:8000/handover/mcp",
    }


async def test_read_tools_are_allowed_and_every_write_asks() -> None:
    settings = json.loads((STAGE / ".claude/settings.json").read_text())
    permissions = await tool_permissions()
    assert sorted(settings["permissions"]["allow"]) == sorted(n for n, read_only in permissions.items() if read_only)
    assert sorted(settings["permissions"]["ask"]) == sorted(n for n, read_only in permissions.items() if not read_only)
    assert sorted(settings["enabledMcpjsonServers"]) == ["petstore-discovery", "petstore-handover", "petstore-sales"]
