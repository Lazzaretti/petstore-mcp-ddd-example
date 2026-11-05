"""eval.py without a model: reading a transcript, judging the before side, the seed."""

import json
from pathlib import Path

import eval as evaluation
from petstore.app import SEED_PETS


def transcript(tmp_path: Path, *events: dict) -> Path:
    path = tmp_path / "run.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in events))
    return path


def tool_use(call_id: str, name: str, **arguments: object) -> dict:
    content = [{"type": "tool_use", "id": call_id, "name": name, "input": arguments}]
    return {"type": "assistant", "message": {"content": content}}


def tool_result(call_id: str, is_error: bool = False) -> dict:
    content = [{"type": "tool_result", "tool_use_id": call_id, "is_error": is_error, "content": "…"}]
    return {"type": "user", "message": {"content": content}}


def test_calls_failures_probing_and_tokens_come_from_the_transcript(tmp_path: Path) -> None:
    path = transcript(
        tmp_path,
        {"type": "system", "claude_code_version": "2.1.316"},
        tool_use("1", "mcp__petstore__findPetsByTags", tags=["friendly"]),
        tool_result("1"),
        tool_use("2", "mcp__petstore__getPetById", petId=7),
        tool_result("2", is_error=True),
        tool_use("3", "mcp__petstore__placeOrder", petId=1),
        tool_result("3"),
        tool_use("4", "mcp__petstore__getOrderById", orderId=1),
        tool_result("4"),
        {
            "type": "result",
            "usage": {"input_tokens": 10, "cache_read_input_tokens": 5, "output_tokens": 3},
            "num_turns": 4,
        },
    )
    run = evaluation.Run(side="before", number=1)
    calls = evaluation.read_transcript(run, path, writes=evaluation.before_write_tools())
    assert (run.tool_calls, run.failed_calls, run.probing_calls) == (4, 1, 2)
    assert (run.input_tokens, run.output_tokens, run.turns) == (15, 3, 4)
    assert run.calls == ["findPetsByTags", "getPetById", "placeOrder", "getOrderById"]
    evaluation.judge_before(run, calls)
    assert run.pet_bought and not run.sold_pet_ordered and not run.success


def test_ordering_the_sold_pet_is_flagged(tmp_path: Path) -> None:
    path = transcript(tmp_path, tool_use("1", "mcp__petstore__placeOrder", petId=4), tool_result("1"))
    run = evaluation.Run(side="before", number=1)
    evaluation.judge_before(run, evaluation.read_transcript(run, path, evaluation.before_write_tools()))
    assert run.sold_pet_ordered and not run.pet_bought


def test_the_before_side_writes_are_the_non_get_operations() -> None:
    writes = evaluation.before_write_tools()
    assert {"placeOrder", "updatePet", "addPet", "deleteOrder"} <= writes
    assert not {"findPetsByTags", "getPetById", "getInventory"} & writes


def test_the_after_side_writes_follow_the_annotations() -> None:
    assert evaluation.after_write_tools() == {"reserve_pet", "buy_pet", "schedule_pickup", "cancel_purchase"}


def test_the_local_petstore_gets_the_same_seed() -> None:
    pets = [evaluation.petstore_pet(p) for p in SEED_PETS]
    assert [(p["id"], p["name"], p["status"]) for p in pets] == [
        (1, "Rex", "available"),
        (2, "Mia", "available"),
        (3, "Bello", "available"),
        (4, "Max", "sold"),
    ]
    assert [t["name"] for t in pets[2]["tags"]] == ["puppy", "friendly"]


def test_without_pickup_the_after_side_writes_are_reserve_buy_cancel() -> None:
    assert evaluation.after_write_tools(pickup=False) == {"reserve_pet", "buy_pet", "cancel_purchase"}


def test_without_pickup_the_table_has_no_pickup_column() -> None:
    runs = [evaluation.Run(side="after", number=1, tool_calls=2, pet_bought=True)]
    with_pickup = evaluation.table("after", runs, pickup=True).splitlines()[2]
    without = evaluation.table("after", runs, pickup=False).splitlines()[2]
    assert "pickup" in with_pickup and "pickup" not in without
    assert "still for sale" in without


def write_result(directory: Path, meta: dict | None, runs: list[evaluation.Run], model_line: str = "") -> None:
    directory.mkdir(parents=True)
    if meta:
        (directory / "meta.json").write_text(json.dumps(meta))
    (directory / "summary.md").write_text(f"# x\n\n{model_line}\n")
    (directory / "runs.json").write_text(json.dumps([evaluation.asdict(r) for r in runs]))


def test_the_combined_summary_covers_every_result_directory(tmp_path: Path) -> None:
    bought = evaluation.Run(side="after", number=1, tool_calls=2, probing_calls=1, input_tokens=100, pet_bought=True)
    on_offer = evaluation.Run(side="before", number=1, tool_calls=4, failed_calls=1, still_on_offer=True)
    write_result(tmp_path / "a", {"model": "claude-haiku-5-5", "pickup": False}, [bought, on_offer])
    # Older results have no meta.json: the model comes from summary.md, pickup was on.
    write_result(
        tmp_path / "b", None, [bought], model_line="Claude Code 2.1.316 headless, model `claude-opus-5-5`, AUTH=off"
    )
    combined = evaluation.combined_summary(tmp_path)
    rows = [line for line in combined.splitlines() if line.startswith("| claude")]
    assert rows == [
        "| claude-haiku-5-5 | off | after | 1 | 2.0 | 1.0 | 0.0 | 100 | 0 | 1/1 | — | 0/1 | [a](a/summary.md) |",
        "| claude-haiku-5-5 | off | before | 1 | 4.0 | 0.0 | 1.0 | 0 | 0 | 0/1 | — | 1/1 | [a](a/summary.md) |",
        "| claude-opus-5-5 | on | after | 1 | 2.0 | 1.0 | 0.0 | 100 | 0 | 1/1 | 0/1 | 0/1 | [b](b/summary.md) |",
    ]
