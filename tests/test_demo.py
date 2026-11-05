"""`app.py demo`: the eight scenes, scripted and deterministic."""

import io

import pytest

from petstore import demo

pytestmark = pytest.mark.anyio


async def run_demo(until: int = 8) -> str:
    out = io.StringIO()
    await demo.run(until=until, out=out)
    return out.getvalue()


def scene(output: str, number: int) -> str:
    start = output.index(f"Scene {number} ")
    end = output.find(f"Scene {number + 1} ", start)
    return output[start : end if end != -1 else None]


async def test_scene_1_lists_the_friendly_dogs_in_domain_words() -> None:
    first = scene(await run_demo(), 1)
    assert "alice" in first and "find_available_pets" in first
    assert '"name": "Rex"' in first and '"name": "Bello"' in first and "Max" not in first


async def test_scene_2_buys_rex_and_lists_free_slots() -> None:
    second = scene(await run_demo(), 2)
    assert 'purchase_id: "pur-00000001"' in second
    assert "Ask the customer, then call schedule_pickup." in second


async def test_scene_3_schedules_the_pickup() -> None:
    assert "Pickup scheduled: Rex at the shop on Tue, Nov 10, 10:00 AM." in scene(await run_demo(), 3)


async def test_scene_4_refuses_rex_to_bob() -> None:
    fourth = scene(await run_demo(), 4)
    assert "bob" in fourth and "PetNotAvailable: Rex is already sold." in fourth


async def test_scene_5_shows_alices_purchase_in_pet_handover() -> None:
    fifth = scene(await run_demo(), 5)
    assert '"purchase_id": "pur-00000001"' in fifth and "Tue, Nov 10, 10:00 AM" in fifth


async def test_scene_6_lets_bellos_reservation_expire() -> None:
    sixth = scene(await run_demo(), 6)
    assert "clock + 25 h" in sixth
    assert "ReservationExpired: Bello's reservation ran out." in sixth
    assert '"name": "Bello"' in sixth  # back on offer


async def test_scene_7_is_too_late_to_move_the_pickup_and_to_cancel() -> None:
    seventh = scene(await run_demo(), 7)
    assert "TooLateToReschedule: Rex was due for pickup on Tue, Nov 10, 10:00 AM." in seventh
    assert "TooLateToCancel: Rex was due for pickup on Tue, Nov 10, 10:00 AM." in seventh
    assert seventh.index("TooLateToReschedule") < seventh.index("TooLateToCancel")


async def test_scene_8_hides_alices_purchase_from_bob() -> None:
    eighth = scene(await run_demo(), 8)
    assert "bob" in eighth and "UnknownPurchase: No purchase with id pur-00000001." in eighth


async def test_the_recording_stops_after_scene_5() -> None:
    output = await run_demo(until=5)
    assert "Scene 5 " in output and "Scene 6 " not in output


async def test_the_demo_is_deterministic() -> None:
    assert await run_demo() == await run_demo()
