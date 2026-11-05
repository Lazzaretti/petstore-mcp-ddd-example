from datetime import datetime
from zoneinfo import ZoneInfo

from petstore.events import EventBus, PetBackOnOffer, PetTakenOffOffer, Slot

DENVER = ZoneInfo("America/Denver")


def test_a_slot_has_an_iso_value_for_the_agent_and_a_us_title_for_people() -> None:
    slot = Slot.at(datetime(2026, 11, 10, 10, 0, tzinfo=DENVER))
    assert slot.value == "2026-11-10T10:00"
    assert slot.title == "Tue, Nov 10, 10:00 AM"


def test_slot_titles_use_the_12_hour_clock() -> None:
    assert Slot.at(datetime(2026, 11, 10, 16, 45, tzinfo=DENVER)).title == "Tue, Nov 10, 4:45 PM"
    assert Slot.at(datetime(2026, 11, 10, 12, 0, tzinfo=DENVER)).title == "Tue, Nov 10, 12:00 PM"


def test_the_bus_runs_handlers_before_publish_returns() -> None:
    bus = EventBus()
    received: list[PetTakenOffOffer] = []
    bus.subscribe(PetTakenOffOffer, received.append)
    bus.publish(PetTakenOffOffer(pet_id=1))
    assert received == [PetTakenOffOffer(pet_id=1)]


def test_the_bus_delivers_only_the_subscribed_event_type() -> None:
    bus = EventBus()
    received: list[PetTakenOffOffer] = []
    bus.subscribe(PetTakenOffOffer, received.append)
    bus.publish(PetBackOnOffer(pet_id=1))
    assert received == []
