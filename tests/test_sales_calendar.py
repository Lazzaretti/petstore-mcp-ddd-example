from datetime import datetime, timedelta

import pytest

from petstore.sales import Clock, PickupCalendar, SlotNotAvailable, reservation_hold_from_env
from tests.factories import DENVER, TALK


def titles(slots: list[datetime]) -> list[str]:
    return [f"{s:%a %H:%M}" for s in slots]


def test_the_earliest_slot_is_10_am_the_next_day_and_six_are_listed() -> None:
    assert titles(PickupCalendar().free_slots(TALK)) == [
        "Tue 10:00",
        "Tue 11:00",
        "Tue 12:00",
        "Tue 13:00",
        "Tue 14:00",
        "Tue 15:00",
    ]


def test_the_last_slot_of_the_day_is_5_pm() -> None:
    slots = PickupCalendar().free_slots(TALK, count=9)
    assert titles(slots)[7:] == ["Tue 17:00", "Wed 10:00"]


def test_the_shop_is_closed_on_sundays() -> None:
    saturday = datetime(2026, 11, 14, 9, 0, tzinfo=DENVER)
    assert titles(PickupCalendar().free_slots(saturday))[0] == "Mon 10:00"


def test_one_pet_per_slot() -> None:
    calendar = PickupCalendar()
    calendar.book(calendar.validate("2026-11-10T10:00", TALK, next_action="x"))
    assert titles(calendar.free_slots(TALK))[0] == "Tue 11:00"


def test_a_released_slot_is_free_again() -> None:
    calendar = PickupCalendar()
    slot = calendar.validate("2026-11-10T10:00", TALK, next_action="x")
    calendar.book(slot)
    calendar.release(slot)
    assert titles(calendar.free_slots(TALK))[0] == "Tue 10:00"


def test_a_taken_slot_is_refused_with_the_free_slots_and_what_to_do() -> None:
    calendar = PickupCalendar()
    calendar.book(calendar.validate("2026-11-10T10:00", TALK, next_action="x"))
    with pytest.raises(SlotNotAvailable) as refused:
        calendar.validate("2026-11-10T10:00", TALK, next_action="Call schedule_pickup with one of them.")
    assert str(refused.value) == (
        "SlotNotAvailable: Tue, Nov 10, 10:00 AM was just taken. Free slots: "
        "Tue, Nov 10, 11:00 AM (2026-11-10T11:00), Tue, Nov 10, 12:00 PM (2026-11-10T12:00), "
        "Tue, Nov 10, 1:00 PM (2026-11-10T13:00), Tue, Nov 10, 2:00 PM (2026-11-10T14:00), "
        "Tue, Nov 10, 3:00 PM (2026-11-10T15:00), Tue, Nov 10, 4:00 PM (2026-11-10T16:00). "
        "Call schedule_pickup with one of them."
    )


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ("2026-11-15T10:00", "Sun, Nov 15, 10:00 AM is not a pickup slot"),
        ("2026-11-10T18:00", "Tue, Nov 10, 6:00 PM is not a pickup slot"),
        ("2026-11-10T09:00", "Tue, Nov 10, 9:00 AM is not a pickup slot"),
        ("2026-11-10T10:30", "Tue, Nov 10, 10:30 AM is not a pickup slot"),
        ("2026-11-09T17:00", "Mon, Nov 9, 5:00 PM is too soon"),
        ("tomorrow", "'tomorrow' is not a slot"),
    ],
)
def test_slots_outside_the_calendar_are_refused(value: str, reason: str) -> None:
    with pytest.raises(SlotNotAvailable, match=f"^SlotNotAvailable: {reason}"):
        PickupCalendar().validate(value, TALK, next_action="x")


def test_a_slot_with_seconds_or_an_offset_means_the_same_shop_time() -> None:
    calendar = PickupCalendar()
    assert calendar.validate("2026-11-10T10:00:00", TALK, next_action="x") == datetime(2026, 11, 10, 10, tzinfo=DENVER)
    assert calendar.validate("2026-11-10T17:00:00Z", TALK, next_action="x") == datetime(2026, 11, 10, 10, tzinfo=DENVER)


def test_a_fixed_clock_can_be_moved_forward() -> None:
    clock = Clock(fixed=TALK)
    clock.advance(timedelta(hours=25))
    assert clock.now() == TALK + timedelta(hours=25)


def test_the_clock_comes_from_petstore_now_in_shop_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PETSTORE_NOW", "2026-11-09T16:45")
    assert Clock.from_env().now() == TALK


def test_the_real_clock_runs_in_shop_time(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PETSTORE_NOW", raising=False)
    assert Clock.from_env().now().tzinfo == DENVER


def test_the_real_clock_cannot_be_moved() -> None:
    with pytest.raises(RuntimeError):
        Clock().advance(timedelta(hours=1))


@pytest.mark.parametrize(
    ("setting", "hold"),
    [
        (None, timedelta(hours=24)),
        ("2h", timedelta(hours=2)),
        ("90s", timedelta(seconds=90)),
        ("5m", timedelta(minutes=5)),
    ],
)
def test_the_reservation_hold_is_configurable(
    monkeypatch: pytest.MonkeyPatch, setting: str | None, hold: timedelta
) -> None:
    if setting is None:
        monkeypatch.delenv("RESERVATION_HOLD", raising=False)
    else:
        monkeypatch.setenv("RESERVATION_HOLD", setting)
    assert reservation_hold_from_env() == hold
