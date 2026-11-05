"""What the host really passes to the model: capture Claude Code's first model request per side.

A tiny logging proxy in front of the Anthropic API. Headless Claude Code runs with
ANTHROPIC_BASE_URL pointing at it, with the same MCP config and flags as the evaluation
(eval.py), once per side: before, after with PICKUP=off, after with pickup. The proxy
forwards every request unchanged and keeps the first model request (the one carrying the
prompt), with auth headers redacted, under eval/results/<timestamp>-host-request/.

    uv run python host_request.py [--model claude-haiku-5-5]
"""

import argparse
import json
import os
import socket
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx2
import uvicorn
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import StreamingResponse
from starlette.routing import Route

import eval as evaluation

UPSTREAM = "https://api.anthropic.com"
SECRET_HEADERS = {"authorization", "x-api-key", "cookie"}
HOP_BY_HOP = {"host", "content-length", "transfer-encoding", "connection"}
SIDES = {"before": ("before", True), "after-no-pickup": ("after", False), "after": ("after", True)}


def redact(headers: dict[str, str]) -> dict[str, str]:
    return {k: ("[redacted]" if k.lower() in SECRET_HEADERS else v) for k, v in headers.items()}


def redact_body(body: dict[str, Any]) -> dict[str, Any]:
    """metadata.user_id carries the account and device ids."""
    if "metadata" in body:
        body = {**body, "metadata": {k: "[redacted]" for k in body["metadata"]}}
    return body


class Recorder:
    """Keeps every model request the proxy forwards (POST …/messages)."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []

    def first_with(self, prompt: str) -> dict[str, Any] | None:
        return next((r for r in self.requests if prompt in json.dumps(r["body"].get("messages", []))), None)


def proxy_app(recorder: Recorder) -> Starlette:
    client = httpx2.AsyncClient(base_url=UPSTREAM, timeout=None)

    async def forward(request: Request) -> StreamingResponse:
        body = await request.body()
        path = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_BY_HOP}
        if request.method == "POST" and request.url.path.endswith("/messages"):
            recorder.requests.append({"path": path, "headers": redact(headers), "body": redact_body(json.loads(body))})
        upstream = await client.send(
            client.build_request(request.method, path, headers=headers, content=body), stream=True
        )
        response_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in HOP_BY_HOP}
        return StreamingResponse(
            upstream.aiter_raw(), status_code=upstream.status_code, headers=response_headers,
            background=BackgroundTask(upstream.aclose),
        )  # fmt: skip

    return Starlette(routes=[Route("/{path:path}", forward, methods=["GET", "POST", "PUT", "DELETE", "HEAD"])])


def start_proxy(recorder: Recorder) -> str:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(proxy_app(recorder), host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)
    return f"http://127.0.0.1:{port}"


def capture(side: str, pickup: bool, model: str, out_dir: Path, name: str) -> dict[str, Any]:
    recorder = Recorder()
    base_url = start_proxy(recorder)
    env = {**os.environ, "ANTHROPIC_BASE_URL": base_url}
    evaluation.forget_cached_auth_state()
    with evaluation.fresh(side, pickup):
        evaluation.run_claude(side, model, out_dir / f"{name}.transcript.jsonl", env=env)
    first = recorder.first_with(evaluation.PROMPT)
    if first is None:
        raise RuntimeError(f"{name}: no model request with the prompt went through the proxy")
    (out_dir / f"{name}.request.json").write_text(json.dumps(first, indent=2, ensure_ascii=False))
    return first


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default="claude-haiku-5-5")
    arguments = parser.parse_args()
    out_dir = evaluation.RESULTS / f"{datetime.now():%Y-%m-%dT%H-%M}-host-request"
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, (side, pickup) in SIDES.items():
        request = capture(side, pickup, arguments.model, out_dir, name)
        tools = [t["name"] for t in request["body"].get("tools", [])]
        print(f"{name}: {len(tools)} tools sent: {', '.join(tools)}")
    print(f"Saved: {out_dir}")


if __name__ == "__main__":
    main()
