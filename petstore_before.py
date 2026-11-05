"""The "before" MCP server: the Swagger Petstore REST API, auto-converted.

A few lines turn a REST API into an MCP server: one tool per endpoint, named after
operationIds. The spec is a pinned local copy (petstore-openapi.json, Swagger Petstore
1.0.29, downloaded 1 Nov 2026), so the tool list doesn't depend on the network.

Tool calls go to PETSTORE_API_URL: the live public Petstore by default, or the local one
seeded with the demo's pets for the evaluation (see eval.py).

Serve it over stdio:   uv run python petstore_before.py
What the agent sees:   uv run python -m petstore.app tools
"""

import json
import os
import pathlib

import httpx2
from fastmcp import FastMCP

LIVE_PETSTORE = "https://petstore3.swagger.io/api/v3"
SPEC = pathlib.Path(__file__).with_name("petstore-openapi.json")


def create_server(base_url: str | None = None) -> FastMCP:
    base_url = base_url or os.environ.get("PETSTORE_API_URL", LIVE_PETSTORE)
    spec = json.loads(SPEC.read_text())
    return FastMCP.from_openapi(openapi_spec=spec, client=httpx2.AsyncClient(base_url=base_url), name="petstore")


if __name__ == "__main__":
    create_server().run()
