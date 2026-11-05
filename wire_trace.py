"""Raw HTTP trace of the three servers for the slides (Streamable HTTP, spec 2026-07-28).

Plain POSTs, no MCP client: every request carries `Mcp-Method` / `Mcp-Name` and its
`_meta` (protocol version, client info), so each message stands on its own.
Start the servers fresh with AUTH=off first: the second buy_pet is refused because
the first one sold Rex.

    AUTH=off uv run python -m petstore.app serve
    uv run python wire_trace.py [--url http://localhost:8000] [--out trace.jsonl]
"""

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any

import httpx2

PROTOCOL_VERSION = "2026-07-28"
CLIENT_INFO = {"name": "wire-trace", "version": "1.0.0"}

# (context, method, params): the fixed call list.
CALLS: list[tuple[str, str, dict[str, Any]]] = [
    *[
        (context, method, {})
        for context in ("discovery", "sales", "handover")
        for method in ("server/discover", "tools/list")
    ],
    ("discovery", "tools/call", {"name": "find_available_pets", "arguments": {"species": "dog", "tag": "friendly"}}),
    ("sales", "tools/call", {"name": "buy_pet", "arguments": {"pet_id": 1}}),
    ("sales", "tools/call", {"name": "buy_pet", "arguments": {"pet_id": 1}}),
    ("sales", "resources/read", {"uri": "pet-sales://policies"}),
]


@dataclass
class Exchange:
    path: str
    method: str
    name: str | None
    request_headers: dict[str, str]
    request: dict[str, Any]
    status: int
    response_headers: dict[str, str]
    response: dict[str, Any]


def name_of(method: str, params: dict[str, Any]) -> str | None:
    """The Mcp-Name header: the tool for tools/call, the URI for resources/read."""
    return params.get("name") if method == "tools/call" else params.get("uri")


def request_headers(method: str, name: str | None) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Mcp-Protocol-Version": PROTOCOL_VERSION,
        "Mcp-Method": method,
    }
    if name:
        headers["Mcp-Name"] = name
    return headers


def request_body(request_id: int, method: str, params: dict[str, Any]) -> dict[str, Any]:
    meta = {
        "io.modelcontextprotocol/protocolVersion": PROTOCOL_VERSION,
        "io.modelcontextprotocol/clientInfo": CLIENT_INFO,
        "io.modelcontextprotocol/clientCapabilities": {},
    }
    return {"jsonrpc": "2.0", "id": request_id, "method": method, "params": {**params, "_meta": meta}}


def parse_response(response: httpx2.Response) -> dict[str, Any]:
    """JSON, or the last `data:` line of an event stream."""
    if response.headers.get("content-type", "").startswith("text/event-stream"):
        data = [line.removeprefix("data:").strip() for line in response.text.splitlines() if line.startswith("data:")]
        return json.loads(data[-1])
    return response.json()


def trace(base_url: str) -> list[Exchange]:
    exchanges = []
    with httpx2.Client(base_url=base_url, timeout=30) as http:
        for request_id, (context, method, params) in enumerate(CALLS, start=1):
            path = f"/{context}/mcp"
            name = name_of(method, params)
            headers = request_headers(method, name)
            body = request_body(request_id, method, params)
            response = http.post(path, headers=headers, json=body)
            exchanges.append(
                Exchange(
                    path,
                    method,
                    name,
                    headers,
                    body,
                    response.status_code,
                    dict(response.headers),
                    parse_response(response),
                )
            )
    return exchanges


def show(exchange: Exchange) -> str:
    mcp_headers = {k: v for k, v in exchange.request_headers.items() if k.startswith("Mcp-")}
    header_line = "  ".join(f"{k}: {v}" for k, v in mcp_headers.items())
    return (
        f"--> POST {exchange.path}  {header_line}\n    {json.dumps(exchange.request)}\n"
        f"<-- HTTP {exchange.status}\n    {json.dumps(exchange.response)}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://localhost:8000", help="base URL; /<context>/mcp is appended")
    parser.add_argument("--out", help="also write the exchanges as JSON lines")
    arguments = parser.parse_args()
    exchanges = trace(arguments.url)
    for exchange in exchanges:
        print(show(exchange))
    if arguments.out:
        with open(arguments.out, "w") as out:
            out.writelines(json.dumps(asdict(e)) + "\n" for e in exchanges)


if __name__ == "__main__":
    main()
