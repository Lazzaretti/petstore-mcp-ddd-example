"""What happened in one take of the before clip, from Claude Code's session transcript and the local Petstore.

Per prompt: the tool calls (name, arguments, error or not) and the agent's last words; pet updates
are printed with the fields they sent. Then Rex in the
local Petstore after the take, compared with the seed: still on offer? sold? fields wiped by updatePet
(which replaces the whole pet)? Usage: uv run python scripts/check_before_take.py --out take.json
"""

import argparse
import json
import os
from pathlib import Path
from typing import Any

import httpx2

import eval as evaluation

STAGE = evaluation.ROOT / "stage-before"


def latest_session(stage: Path = STAGE) -> Path:
    config = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude"))
    sessions = config / "projects" / str(stage).replace("/", "-").replace(".", "-")
    return max(sessions.glob("*.jsonl"), key=lambda path: path.stat().st_mtime)


def prompt_text(message: dict[str, Any]) -> str | None:
    content = message.get("content")
    if isinstance(content, str):
        return content
    texts = [part.get("text", "") for part in content or [] if part.get("type") == "text"]
    return "".join(texts) if texts and not any(part.get("type") == "tool_result" for part in content) else None


def result_text(tool_result: dict[str, Any]) -> str:
    content = tool_result.get("content")
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content or [] if part.get("type") == "text")


def turns(session: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    calls: dict[str, dict[str, Any]] = {}
    for line in session.read_text().splitlines():
        entry = json.loads(line)
        message = entry.get("message") or {}
        if entry.get("type") == "user":
            text = prompt_text(message)
            if text and not text.startswith("<"):
                result.append({"prompt": text, "calls": [], "answer": ""})
                continue
            for part in message.get("content") or []:
                if isinstance(part, dict) and part.get("type") == "tool_result" and part["tool_use_id"] in calls:
                    call = calls[part["tool_use_id"]]
                    call["error"] = bool(part.get("is_error"))
                    if call["error"]:
                        call["error_text"] = result_text(part)
        elif entry.get("type") == "assistant" and result:
            for part in message.get("content") or []:
                if part.get("type") == "tool_use":
                    call = {"tool": part["name"].split("__")[-1], "input": part["input"], "error": None}
                    calls[part["id"]] = call
                    result[-1]["calls"].append(call)
                elif part.get("type") == "text" and part["text"].strip():
                    result[-1]["answer"] = part["text"].strip()
    return result


def rex_after(base_url: str) -> dict[str, Any]:
    seed = evaluation.petstore_pet(evaluation.SEED_PETS[0])
    with httpx2.Client(base_url=base_url, timeout=30) as http:
        rex = http.get("/pet/1").json()
        friendly = http.get("/pet/findByTags", params={"tags": "friendly"}).json()
    return {
        "status": rex.get("status"),
        "listed_as_available": any(p["id"] == 1 and p.get("status") == "available" for p in friendly),
        "changed_fields": sorted(k for k in seed if k != "status" and rex.get(k) != seed[k]),
        "pet": rex,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    arguments = parser.parse_args()
    session = latest_session()
    report = {"session": session.name, "turns": turns(session), "rex_after": rex_after(evaluation.LOCAL_PETSTORE)}
    arguments.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    for number, turn in enumerate(report["turns"], start=1):
        chain = " → ".join(c["tool"] + (" (error)" if c["error"] else "") for c in turn["calls"]) or "(no calls)"
        print(f"({number}) {turn['prompt']}\n    {chain}\n    {turn['answer'][:300]!r}")
        for call in turn["calls"]:
            if call["tool"] in ("updatePet", "updatePetWithForm"):
                print(f"    {call['tool']} sent: {json.dumps(call['input'], ensure_ascii=False)}")
    rex = report["rex_after"]
    print(f"Rex after the take: {rex['status']}, changed fields: {rex['changed_fields'] or 'none'}")


if __name__ == "__main__":
    main()
