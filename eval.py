"""Evaluation "Buy me a friendly dog": the same prompt, before and after, with headless Claude Code.

Measures what the agent does, never stages it: tool calls, failed calls, probing calls
(reads before the first write), tokens, cost, and whether a pet was bought and its pickup
scheduled. Both sides start from the same four pets (the before side against a local
Petstore, see scripts/petstore-local.sh) and are reset before each run.

    uv run python eval.py run [--runs 5] [--side before|after|both] [--model claude-opus-5-5] [--pickup on|off]
    uv run python eval.py combine                                      # eval/results/combined.md
    uv run python eval.py seed --url http://localhost:8081/api/v3     # used by petstore-local.sh

Results and transcripts: eval/results/<timestamp>/.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

import httpx2

from petstore.app import SEED_PETS, SeedPet

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "eval" / "results"
PROMPT = "Buy me a friendly dog."
# Headless runs have no one to answer questions; the same note goes to both sides.
NO_CUSTOMER_IN_THE_LOOP = (
    "The customer is not available to answer questions during this run. Where you would ask them, "
    "decide yourself with the first sensible option and say what you chose."
)
LOCAL_PETSTORE = "http://localhost:8081/api/v3"
# Not 8000: Claude Code keeps OAuth state per server name and URL, so a login against the stage
# app on 8000 would make these AUTH=off servers look like OAuth servers. 8010 also leaves a running
# stage app alone.
AFTER_PORT = 8010
AFTER_SERVERS = ("petstore-discovery", "petstore-sales", "petstore-handover")
CLAUDE_CODE_VERSION = "2.1.316"


# --- the local Petstore's data ---------------------------------------------------------------------


def petstore_pet(pet: SeedPet) -> dict[str, Any]:
    category = {"dog": {"id": 1, "name": "Dogs"}, "cat": {"id": 2, "name": "Cats"}}[pet.species]
    return {
        "id": pet.pet_id,
        "name": pet.name,
        "category": category,
        "photoUrls": [],
        "tags": [{"id": i, "name": tag} for i, tag in enumerate(pet.tags, start=1)],
        "status": "sold" if pet.sold else "available",
    }


def seed_local_petstore(base_url: str) -> None:
    """Our four pets as pets 1-4; the image's other sample pets are removed."""
    with httpx2.Client(base_url=base_url, timeout=30) as http:
        for pet in SEED_PETS:
            http.put("/pet", json=petstore_pet(pet)).raise_for_status()
        for pet_id in range(len(SEED_PETS) + 1, 11):
            http.delete(f"/pet/{pet_id}", headers={"api_key": "special-key"})


# --- one side: how to reset it, how Claude Code reaches it, how to read the outcome ----------------


@dataclass
class Run:
    side: str
    number: int
    tool_calls: int = 0
    failed_calls: int = 0
    probing_calls: int = 0
    calls: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    turns: int = 0
    pet_bought: bool = False
    pickup_scheduled: bool = False
    sold_pet_ordered: bool = False
    still_on_offer: bool = False  # the bought pet can still be found and bought by someone else
    final_answer: str = ""

    @property
    def success(self) -> bool:
        return self.pet_bought and self.pickup_scheduled


def before_write_tools() -> set[str]:
    """Every operation that isn't a GET changes something."""
    spec = json.loads((ROOT / "petstore-openapi.json").read_text())
    return {
        operation["operationId"]
        for path in spec["paths"].values()
        for method, operation in path.items()
        if method != "get"
    }


def after_write_tools(pickup: bool = True) -> set[str]:
    import asyncio

    from fastmcp import Client

    from petstore.app import create_petstore, create_servers

    async def writes() -> set[str]:
        names = set()
        for server in create_servers(create_petstore(pickup=pickup)).values():
            async with Client(server) as client:
                names |= {t.name for t in await client.list_tools() if not t.annotations.read_only_hint}
        return names

    os.environ["AUTH"] = "off"
    return asyncio.run(writes())


def mcp_config(side: str) -> dict[str, Any]:
    if side == "before":
        command = ["uv", "run", "--directory", str(ROOT), "python", "petstore_before.py"]
        server = {"command": command[0], "args": command[1:], "env": {"PETSTORE_API_URL": LOCAL_PETSTORE}}
        return {"mcpServers": {"petstore": server}}
    urls = {name: f"http://localhost:{AFTER_PORT}/{name.removeprefix('petstore-')}/mcp" for name in AFTER_SERVERS}
    return {"mcpServers": {name: {"type": "http", "url": url} for name, url in urls.items()}}


def allowed_tools(side: str) -> list[str]:
    return ["mcp__petstore"] if side == "before" else [f"mcp__{name}" for name in AFTER_SERVERS]


@contextmanager
def fresh(side: str, pickup: bool) -> Iterator[None]:
    """Reset = a fresh local Petstore (before) or a fresh app process (after)."""
    if side == "before":
        subprocess.run([ROOT / "scripts/petstore-local.sh", "start"], check=True, capture_output=True)
        yield
        return
    env = {**os.environ, "AUTH": "off", "PETSTORE_CUSTOMER": "alice", "PORT": str(AFTER_PORT)}
    env["PICKUP"] = "on" if pickup else "off"
    env.pop("PETSTORE_NOW", None)
    app = subprocess.Popen(
        [sys.executable, "-m", "petstore.app", "serve"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_for(f"http://localhost:{AFTER_PORT}/sales/stock")
        yield
    finally:
        app.terminate()
        app.wait(timeout=10)


def _wait_for(url: str, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            httpx2.get(url, timeout=2)
            return
        except httpx2.TransportError:
            time.sleep(0.2)
    raise TimeoutError(url)


def forget_cached_auth_state() -> None:
    """Claude Code caches "needs auth" per server name; a stale entry from an OAuth session would
    silently drop the AUTH=off servers from the run."""
    cache = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")) / "mcp-needs-auth-cache.json"
    if not cache.exists():
        return
    entries = json.loads(cache.read_text())
    for name in (*AFTER_SERVERS, "petstore"):
        entries.pop(name, None)
    cache.write_text(json.dumps(entries))


# --- running Claude Code and reading its transcript ------------------------------------------------


def run_claude(side: str, model: str, transcript: Path, env: dict[str, str] | None = None) -> None:
    # Outside the repo, so Claude Code loads no CLAUDE.md that would tell the agent about the demo.
    with tempfile.TemporaryDirectory(prefix=f"eval-{side}-") as workdir:
        config = Path(workdir) / "mcp.json"
        config.write_text(json.dumps(mcp_config(side)))
        command = [
            "claude", "-p", PROMPT,
            "--output-format", "stream-json", "--verbose",
            "--model", model,
            "--mcp-config", str(config), "--strict-mcp-config",
            "--tools", "",
            "--allowedTools", *allowed_tools(side),
            "--setting-sources", "",
            "--no-session-persistence",
            "--append-system-prompt", NO_CUSTOMER_IN_THE_LOOP,
        ]  # fmt: skip
        with transcript.open("w") as out:
            subprocess.run(
                command,
                cwd=workdir,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=subprocess.DEVNULL,
                timeout=900,
            )


def tool_name(full_name: str) -> str:
    return full_name.split("__", 2)[-1]


def read_transcript(run: Run, transcript: Path, writes: set[str]) -> dict[str, dict[str, Any]]:
    """Fills in the counts; returns each tool call by id (name, input, isError, result text)."""
    calls: dict[str, dict[str, Any]] = {}
    seen_write = False
    for line in transcript.read_text().splitlines():
        event = json.loads(line)
        if event.get("type") == "system" and event.get("claude_code_version") not in (None, CLAUDE_CODE_VERSION):
            raise RuntimeError(f"Claude Code {event['claude_code_version']}, expected {CLAUDE_CODE_VERSION}")
        if event.get("type") == "result":
            usage = event.get("usage", {})
            run.input_tokens = sum(
                usage.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
            )
            run.output_tokens = usage.get("output_tokens", 0)
            run.cost_usd = event.get("total_cost_usd", 0.0)
            run.turns = event.get("num_turns", 0)
            run.final_answer = event.get("result", "")
        for block in event.get("message", {}).get("content", []) if isinstance(event.get("message"), dict) else []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block["name"].startswith("mcp__"):
                name = tool_name(block["name"])
                calls[block["id"]] = {"name": name, "input": block.get("input", {}), "is_error": False, "text": ""}
                run.tool_calls += 1
                run.calls.append(name)
                if name in writes:
                    seen_write = True
                elif not seen_write:
                    run.probing_calls += 1
            if block.get("type") == "tool_result" and block.get("tool_use_id") in calls:
                call = calls[block["tool_use_id"]]
                call["is_error"] = bool(block.get("is_error"))
                call["text"] = json.dumps(block.get("content"))
                run.failed_calls += call["is_error"]
    return calls


def judge_before(run: Run, calls: dict[str, dict[str, Any]], base_url: str | None = None) -> None:
    """The before API has no customer and no pickup: bought = an order for a friendly dog that was on offer.

    With `base_url`, also asks the Petstore whether an ordered pet is still `available`.
    """
    friendly_on_offer = {p.pet_id for p in SEED_PETS if p.species == "dog" and "friendly" in p.tags and not p.sold}
    sold = {p.pet_id for p in SEED_PETS if p.sold}
    ordered = {
        call["input"].get("petId") for call in calls.values() if call["name"] == "placeOrder" and not call["is_error"]
    }
    run.pet_bought = bool(ordered & friendly_on_offer)
    run.sold_pet_ordered = bool(ordered & sold)
    if base_url:
        statuses = [
            httpx2.get(f"{base_url}/pet/{pet_id}").json().get("status") for pet_id in ordered & friendly_on_offer
        ]
        run.still_on_offer = "available" in statuses


def judge_after(run: Run) -> None:
    """Pet Handover knows: an active purchase for alice, with or without a pickup slot."""
    import asyncio

    from fastmcp import Client

    async def alices_purchases() -> list[dict[str, Any]]:
        async with Client(f"http://localhost:{AFTER_PORT}/handover/mcp") as handover:
            return (await handover.call_tool("my_purchases", {})).structured_content["result"]

    async def on_offer() -> list[str]:
        async with Client(f"http://localhost:{AFTER_PORT}/discovery/mcp") as discovery:
            return [
                p["name"] for p in (await discovery.call_tool("find_available_pets", {})).structured_content["result"]
            ]

    purchases = asyncio.run(alices_purchases())
    run.pet_bought = bool(purchases)
    run.pickup_scheduled = any(p.get("pickup") for p in purchases)  # no pickup field with PICKUP=off
    run.still_on_offer = bool({p["pet"] for p in purchases} & set(asyncio.run(on_offer())))


def evaluate(side: str, number: int, model: str, pickup: bool, out_dir: Path) -> Run:
    run = Run(side=side, number=number)
    writes = before_write_tools() if side == "before" else after_write_tools(pickup)
    transcript = out_dir / f"{side}-{number}.jsonl"
    forget_cached_auth_state()
    with fresh(side, pickup):
        run_claude(side, model, transcript)
        calls = read_transcript(run, transcript, writes)
        if side == "before":
            judge_before(run, calls, LOCAL_PETSTORE)
        else:
            judge_after(run)
    return run


# --- the tables for the numbers slide --------------------------------------------------------------


@dataclass(frozen=True)
class Column:
    name: str
    cell: Callable[[Run], str]
    average: Callable[[list[Run]], str]


def _mean(attribute: str, spec: str) -> Callable[[list[Run]], str]:
    return lambda runs: format(mean(getattr(r, attribute) for r in runs), spec)


def _count(attribute: str) -> Callable[[list[Run]], str]:
    return lambda runs: f"{sum(getattr(r, attribute) for r in runs)}/{len(runs)}"


def _yes(attribute: str) -> Callable[[Run], str]:
    return lambda run: "yes" if getattr(run, attribute) else "no"


PICKUP_COLUMN = "pickup"
COLUMNS = (
    Column("run", lambda r: str(r.number), lambda runs: "⌀"),
    Column("tool calls", lambda r: str(r.tool_calls), _mean("tool_calls", ".1f")),
    Column("failed", lambda r: str(r.failed_calls), _mean("failed_calls", ".1f")),
    Column("reads before 1st write", lambda r: str(r.probing_calls), _mean("probing_calls", ".1f")),
    Column("tokens in", lambda r: f"{r.input_tokens:,}", _mean("input_tokens", ",.0f")),
    Column("tokens out", lambda r: f"{r.output_tokens:,}", _mean("output_tokens", ",.0f")),
    Column("cost $", lambda r: f"{r.cost_usd:.3f}", _mean("cost_usd", ".3f")),
    Column("pet bought", _yes("pet_bought"), _count("pet_bought")),
    Column(PICKUP_COLUMN, _yes("pickup_scheduled"), _count("pickup_scheduled")),
    Column("still for sale", _yes("still_on_offer"), _count("still_on_offer")),
    Column("sold pet ordered", _yes("sold_pet_ordered"), _count("sold_pet_ordered")),
)


def _markdown_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def table(side: str, runs: list[Run], pickup: bool = True) -> str:
    columns = [c for c in COLUMNS if pickup or c.name != PICKUP_COLUMN]
    rows = [_markdown_row([c.name for c in columns]), "|" + "---|" * len(columns)]
    rows += [_markdown_row([c.cell(r) for c in columns]) for r in runs]
    rows.append(_markdown_row([c.average(runs) for c in columns]))
    calls = [f"- run {r.number}: {' → '.join(r.calls) or '(no tool calls)'}" for r in runs]
    return f"### {side}\n\n" + "\n".join(rows) + "\n\nCall chains:\n\n" + "\n".join(calls) + "\n"


def run_evaluation(sides: list[str], runs: int, model: str, pickup: bool) -> Path:
    stamp = datetime.now().strftime("%Y-%m-%dT%H-%M")
    out_dir = RESULTS / f"{stamp}_{model}_pickup-{'on' if pickup else 'off'}"
    out_dir.mkdir(parents=True, exist_ok=True)
    report = [
        f"# Buy me a friendly dog: {runs} runs per side",
        "",
        f"Claude Code {CLAUDE_CODE_VERSION} headless (`claude -p`), model `{model}`, AUTH=off, "
        f"PICKUP={'on' if pickup else 'off'}, prompt: “{PROMPT}”",
        f"Appended system prompt (both sides): “{NO_CUSTOMER_IN_THE_LOOP}”",
        "",
        "failed = isError results (HTTP errors on the before side);",
        "pickup: the before API has no pickup, so it is always no there;" if pickup else "no pickup on either side;",
        "still for sale: after the run, anyone can still buy the bought pet (Petstore status, find_available_pets).",
        "",
    ]
    all_runs = []
    for side in sides:
        side_runs = []
        for number in range(1, runs + 1):
            print(f"{side} run {number}/{runs} …", flush=True)
            side_runs.append(evaluate(side, number, model, pickup, out_dir))
        all_runs += side_runs
        report.append(table(side, side_runs, pickup))
    (out_dir / "meta.json").write_text(json.dumps({"model": model, "pickup": pickup, "runs": runs, "prompt": PROMPT}))
    (out_dir / "summary.md").write_text("\n".join(report))
    (out_dir / "runs.json").write_text(json.dumps([asdict(r) for r in all_runs], indent=2))
    return out_dir


# --- all runs in one table ---------------------------------------------------------------------------


def _meta(directory: Path) -> dict[str, Any]:
    """meta.json, or for older results the model from summary.md (they all ran with pickup)."""
    if (directory / "meta.json").exists():
        return json.loads((directory / "meta.json").read_text())
    model = re.search(r"model `([^`]+)`", (directory / "summary.md").read_text())
    return {"model": model[1] if model else "?", "pickup": True}


def combined_summary(results: Path = RESULTS) -> str:
    rows = []
    for directory in sorted(d for d in results.iterdir() if (d / "runs.json").exists()):
        meta = _meta(directory)
        runs = [Run(**r) for r in json.loads((directory / "runs.json").read_text())]
        for side in sorted({r.side for r in runs}):
            side_runs = [r for r in runs if r.side == side]
            rows.append((meta["model"], "on" if meta["pickup"] else "off", side, side_runs, directory.name))
    header = [
        "model", "PICKUP", "side", "runs", "⌀ tool calls", "⌀ reads before 1st write", "⌀ failed",
        "⌀ tokens in", "⌀ tokens out", "pet bought", "pickup", "still for sale", "results",
    ]  # fmt: skip
    lines = [
        "# Buy me a friendly dog: all runs",
        "",
        f"Claude Code {CLAUDE_CODE_VERSION} headless, AUTH=off, same prompt and appended system prompt in every run.",
        "PICKUP=off compares the same scope as the original Petstore API (no pickup on either side).",
        "",
        _markdown_row(header),
        "|" + "---|" * len(header),
    ]
    for model, pickup, side, runs, name in sorted(rows, key=lambda row: row[:3]):
        lines.append(
            _markdown_row(
                [
                    model,
                    pickup,
                    side,
                    str(len(runs)),
                    _mean("tool_calls", ".1f")(runs),
                    _mean("probing_calls", ".1f")(runs),
                    _mean("failed_calls", ".1f")(runs),
                    _mean("input_tokens", ",.0f")(runs),
                    _mean("output_tokens", ",.0f")(runs),
                    _count("pet_bought")(runs),
                    _count("pickup_scheduled")(runs) if pickup == "on" else "—",
                    _count("still_on_offer")(runs),
                    f"[{name}]({name}/summary.md)",
                ]
            )
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run the evaluation")
    run.add_argument("--runs", type=int, default=5)
    run.add_argument("--side", choices=["before", "after", "both"], default="both")
    run.add_argument("--model", default="claude-opus-5-5")
    run.add_argument("--pickup", choices=["on", "off"], default="on", help="off: no pickup on the after side")
    commands.add_parser("combine", help=f"write {RESULTS.relative_to(ROOT)}/combined.md from all results")
    seed = commands.add_parser("seed", help="seed the local Petstore with the demo's pets")
    seed.add_argument("--url", default=LOCAL_PETSTORE)
    arguments = parser.parse_args()
    if arguments.command == "seed":
        seed_local_petstore(arguments.url)
        print(f"seeded {arguments.url}: " + ", ".join(p.name for p in SEED_PETS))
        return
    if arguments.command == "combine":
        (RESULTS / "combined.md").write_text(combined_summary())
        print((RESULTS / "combined.md").read_text())
        return
    sides = ["before", "after"] if arguments.side == "both" else [arguments.side]
    out_dir = run_evaluation(sides, arguments.runs, arguments.model, arguments.pickup == "on")
    print((out_dir / "summary.md").read_text())
    print(f"Transcripts: {out_dir}")


if __name__ == "__main__":
    main()
