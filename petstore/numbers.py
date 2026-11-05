"""`app.py tools`: what the agent sees, before and after, with one formula for both sides.

Size = what the host passes to the model, measured from Claude Code 2.1.316's first model
request (host_request.py): per tool only name (as `mcp__<server>__<tool>`), description and
inputSchema, compact JSON; the server instructions folded into the system prompt as
"## <server>\n<instructions>". Title, annotations, outputSchema and _meta never reach the
model, and resources are not listed. The complete tools/list entries plus instructions
("on the wire") stay as a second number for the footnote.
"""

import json
import os
from collections.abc import Callable
from dataclasses import dataclass

from fastmcp import Client, FastMCP
from mcp_types import Tool

import petstore_before
from petstore.app import create_petstore, create_servers

TOKEN_MODEL = "claude-opus-5-5"
HOST = "Claude Code 2.1.316"


@dataclass(frozen=True)
class ToolSize:
    name: str
    size: int  # sent to the model
    wire_size: int  # the complete tools/list entry
    has_output_schema: bool


@dataclass(frozen=True)
class ServerSize:
    name: str
    tools: list[ToolSize]
    resources: int
    instructions: str
    sent: str  # what the host passes to the model: the size and the token count
    wire: str  # the complete tools/list entries + instructions

    @property
    def size(self) -> int:
        return len(self.sent)

    @property
    def wire_size(self) -> int:
        return len(self.wire)


def _compact(value: object) -> str:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def tool_as_sent(server: str, tool: Tool) -> str:
    return _compact(
        {
            "name": f"mcp__{server}__{tool.name}",
            "description": tool.description or "",
            "input_schema": tool.input_schema,
        }
    )


def instructions_as_sent(server: ServerSize) -> str:
    return f"## {server.name}\n{server.instructions}" if server.instructions else ""


async def measure(server: FastMCP) -> ServerSize:
    async with Client(server) as client:
        tools = await client.list_tools()
        resources = await client.list_resources()
        instructions = client.instructions or ""
        name = client.server_info.name
    wire = [json.dumps(tool.model_dump(mode="json", by_alias=True, exclude_none=True)) for tool in tools]
    sent = [tool_as_sent(name, tool) for tool in tools]
    measured = ServerSize(
        name=name,
        tools=[
            ToolSize(t.name, len(s), len(w), t.output_schema is not None)
            for t, s, w in zip(tools, sent, wire, strict=True)
        ],
        resources=len(resources),
        instructions=instructions,
        sent="".join(sent),
        wire="".join(wire) + instructions,
    )
    return ServerSize(**{**measured.__dict__, "sent": measured.sent + instructions_as_sent(measured)})


def estimate_tokens(text: str) -> int:
    return round(len(text) / 4)


def count_tokens_with_anthropic(text: str) -> int:
    """Anthropic's token-counting endpoint, minus the count of an empty message."""
    import anthropic  # optional: uv run --with anthropic python -m petstore.app tools

    client = anthropic.Anthropic()

    def count(content: str) -> int:
        messages = [{"role": "user", "content": content}]
        return client.messages.count_tokens(model=TOKEN_MODEL, messages=messages).input_tokens

    return count(text) - count(".")


def default_token_counter() -> tuple[Callable[[str], int], str]:
    """The real count when the SDK and a key are there; otherwise chars ÷ 4, marked ≈."""
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return estimate_tokens, "≈"
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return estimate_tokens, "≈"
    return count_tokens_with_anthropic, ""


def _tool_lines(server: ServerSize) -> list[str]:
    count = f"{len(server.tools)} tool{'' if len(server.tools) == 1 else 's'}"
    lines = [f"  {server.name} ({count}, {server.size:,} chars sent, {server.wire_size:,} on the wire)"]
    for tool in server.tools:
        schema = "" if tool.has_output_schema else "   (no outputSchema)"
        lines.append(f"    {tool.name:28} {tool.size:6,} chars sent {tool.wire_size:6,} on the wire{schema}")
    return lines


def _row(label: str, *values: object) -> str:
    return f"{label:46}" + "".join(f" {value!s:>20}" for value in values)


async def _measure_after(pickup: bool) -> list[ServerSize]:
    return [await measure(server) for server in create_servers(create_petstore(pickup=pickup)).values()]


async def report(token_counter: Callable[[str], int] | None = None, mark: str = "≈") -> str:
    """Before next to after with pickup and after without pickup (the original API's scope)."""
    if token_counter is None:
        token_counter, mark = default_token_counter()
    before = [await measure(petstore_before.create_server())]
    sides = [before, await _measure_after(pickup=True), await _measure_after(pickup=False)]
    labels = ["before", "after", "after, no pickup"]

    def tools(servers: list[ServerSize]) -> list[ToolSize]:
        return [tool for server in servers for tool in server.tools]

    def tokens(servers: list[ServerSize]) -> str:
        return f"{mark}{sum(token_counter(s.sent) for s in servers):,}"

    def per_side(value: Callable[[list[ServerSize]], object]) -> list[object]:
        return [value(side) for side in sides]

    # The one server needed to buy: the whole before server, Pet Sales on the after side.
    buying = [[next(s for s in side if s.name in ("petstore", "petstore-sales"))] for side in sides]

    lines = ["What the agent sees", ""]
    for label, side in zip(labels, sides, strict=True):
        lines.append(f"Tools per server, {label}:")
        for server in side:
            lines += _tool_lines(server)
    lines += [
        "",
        _row("", *labels),
        _row("Servers (entry points the host configures)", *per_side(len)),
        _row("Tools", *per_side(lambda side: len(tools(side)))),
        _row("Resources", *per_side(lambda side: sum(s.resources for s in side))),
        _row(
            "Tools with outputSchema",
            *per_side(lambda side: f"{sum(t.has_output_schema for t in tools(side))} of {len(tools(side))}"),
        ),
        _row("Sent to the model (chars)", *per_side(lambda side: f"{sum(s.size for s in side):,}")),
        _row("Tokens sent", *per_side(tokens)),
        _row("On the wire, tools/list + instructions (chars)", *per_side(lambda s: f"{sum(x.wire_size for x in s):,}")),
        "",
        "One server vs. one server (the one needed to buy):",
        _row("", *(f"{b[0].name} ({len(b[0].tools)})" for b in buying)),
        _row("Sent to the model (chars)", *(f"{b[0].size:,}" for b in buying)),
        _row("Tokens sent", *(tokens(b) for b in buying)),
        _row("On the wire (chars)", *(f"{b[0].wire_size:,}" for b in buying)),
        "",
        f"Sent = what {HOST} passes to the model: name, description, inputSchema per tool + server instructions."
        " Not sent: title, annotations, outputSchema, _meta, resources.\n"
        + ("Tokens ≈ chars ÷ 4 (no Anthropic API key)." if mark else f"Tokens: count_tokens, {TOKEN_MODEL}."),
    ]
    return "\n".join(lines)
