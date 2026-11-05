"""The numbers slide: the same formula on both sides."""

import json
import re
from pathlib import Path

import pytest
from fastmcp import Client, FastMCP

import petstore_before
from petstore import numbers
from petstore.app import create_petstore, create_servers

pytestmark = pytest.mark.anyio


async def test_the_before_server_is_19_endpoint_tools_from_the_pinned_spec() -> None:
    measured = await numbers.measure(petstore_before.create_server())
    assert measured.name == "petstore"
    assert len(measured.tools) == 19
    assert sum(t.has_output_schema for t in measured.tools) == 14
    assert "placeOrder" in [t.name for t in measured.tools]


async def test_the_wire_size_is_the_complete_tools_list_entries() -> None:
    # 16,642 chars: the 1 Nov measurement of the before side (full entries incl. output schemas).
    assert (await numbers.measure(petstore_before.create_server())).wire_size == 16_642


async def test_the_wire_size_adds_the_server_instructions() -> None:
    server = FastMCP("x", instructions="Twelve chars")

    @server.tool
    def ping() -> str:
        return "pong"

    measured = await numbers.measure(server)
    [entry] = measured.tools
    assert measured.wire_size == entry.wire_size + len("Twelve chars")


async def test_the_size_counts_only_name_description_and_input_schema_as_the_host_sends_them() -> None:
    server = FastMCP("x", instructions="Twelve chars")

    @server.tool(title="A title", annotations={"readOnlyHint": True})
    def ping() -> str:
        """Ping."""
        return "pong"

    [tool] = (await numbers.measure(server)).tools
    async with Client(server) as client:
        [listed] = await client.list_tools()
    sent = {"name": "mcp__x__ping", "description": "Ping.", "input_schema": listed.input_schema}
    assert tool.size == len(json.dumps(sent, separators=(",", ":")))
    assert tool.wire_size > tool.size  # title, annotations and outputSchema stay on the wire


async def test_the_size_adds_the_instructions_as_the_host_folds_them_into_the_system_prompt() -> None:
    server = FastMCP("x", instructions="Twelve chars")
    measured = await numbers.measure(server)
    assert measured.size == len("## x\nTwelve chars")
    assert (await numbers.measure(FastMCP("y"))).size == 0


# The captured first model request of Claude Code 2.1.316 (host_request.py), one per side.
CAPTURE = sorted((Path(__file__).parents[1] / "eval" / "results").glob("*-host-request"))[-1]
SIDES = {"before": None, "after": True, "after-no-pickup": False}


def servers_of(side: str) -> list[FastMCP]:
    if SIDES[side] is None:
        return [petstore_before.create_server()]
    return list(create_servers(create_petstore(pickup=SIDES[side])).values())


def captured(side: str) -> dict:
    return json.loads((CAPTURE / f"{side}.request.json").read_text())["body"]


@pytest.mark.parametrize("side", SIDES)
async def test_the_formula_reproduces_what_claude_code_sent_to_the_model(side: str) -> None:
    request = captured(side)
    sent_tools = {t["name"]: t for t in request["tools"] if t["name"].startswith("mcp__")}
    sent_text = json.dumps(request["messages"], ensure_ascii=False)
    for server in servers_of(side):
        measured = await numbers.measure(server)
        tools_size = 0
        for tool in measured.tools:
            entry = sent_tools.pop(f"mcp__{measured.name}__{tool.name}")
            assert tool.size == len(json.dumps(entry, separators=(",", ":"), ensure_ascii=False)), tool.name
            tools_size += tool.size
        instructions = numbers.instructions_as_sent(measured)
        assert json.dumps(instructions, ensure_ascii=False)[1:-1] in sent_text
        assert measured.size == tools_size + len(instructions)
    assert sent_tools == {}, "every MCP tool sent is counted"


async def test_the_report_shows_the_wire_size_as_a_second_line() -> None:
    report = await numbers.report(token_counter=numbers.estimate_tokens)
    assert re.search(r"^Sent to the model \(chars\)\s+\d", report, re.M)
    assert re.search(r"^On the wire, tools/list \+ instructions \(chars\)\s+16,642", report, re.M)


async def test_the_after_side_is_6_tools_and_1_resource_on_3_servers() -> None:
    measured = [await numbers.measure(s) for s in create_servers().values()]
    assert [m.name for m in measured] == ["petstore-discovery", "petstore-sales", "petstore-handover"]
    assert sum(len(m.tools) for m in measured) == 6
    assert sum(m.resources for m in measured) == 1
    assert all(t.has_output_schema for m in measured for t in m.tools)


async def test_the_report_puts_both_sides_next_to_each_other() -> None:
    report = await numbers.report(token_counter=numbers.estimate_tokens)
    assert "Servers (entry points the host configures)" in report
    assert "petstore-sales" in report
    assert "≈" in report


def test_without_an_api_key_tokens_are_estimated_as_chars_over_4() -> None:
    assert numbers.estimate_tokens(json.dumps("x" * 398)) == 100


async def test_without_pickup_the_after_side_is_5_tools_with_3_on_pet_sales() -> None:
    measured = [await numbers.measure(s) for s in create_servers(create_petstore(pickup=False)).values()]
    assert sum(len(m.tools) for m in measured) == 5
    assert [len(m.tools) for m in measured] == [1, 3, 1]


async def test_the_report_shows_both_after_variants_next_to_before() -> None:
    report = await numbers.report(token_counter=numbers.estimate_tokens)
    header = next(line for line in report.splitlines() if "before" in line and "after" in line)
    assert header.split() == ["before", "after", "after,", "no", "pickup"]
    tools_row = next(line for line in report.splitlines() if re.match(r"Tools\s+\d", line))
    assert tools_row.split()[-3:] == ["19", "6", "5"]
