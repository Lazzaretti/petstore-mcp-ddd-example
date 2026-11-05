"""Shared test setup: the seed pets, a fixed clock at the talk (Mon Nov 9, 4:45 PM) and a recording bus."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from petstore.events import Event, EventBus
from petstore.sales import Clock, Pet, PetSales, PetStatus

DENVER = ZoneInfo("America/Denver")
TALK = datetime(2026, 11, 9, 16, 45, tzinfo=DENVER)


def seed_pets() -> list[Pet]:
    return [
        Pet(1, "Rex", "dog", ("friendly",), PetStatus.AVAILABLE),
        Pet(2, "Mia", "cat", ("indoor",), PetStatus.AVAILABLE),
        Pet(3, "Bello", "dog", ("puppy", "friendly"), PetStatus.AVAILABLE),
        Pet(4, "Max", "dog", ("friendly",), PetStatus.SOLD),
    ]


class RecordingBus(EventBus):
    def __init__(self) -> None:
        super().__init__()
        self.published: list[Event] = []

    def publish(self, event: Event) -> None:
        self.published.append(event)
        super().publish(event)


def pet_sales(
    now: datetime = TALK, hold: timedelta = timedelta(hours=24), pickup: bool = True
) -> tuple[PetSales, RecordingBus, Clock]:
    bus = RecordingBus()
    clock = Clock(fixed=now)
    return PetSales(seed_pets(), bus=bus, clock=clock, reservation_hold=hold, pickup=pickup), bus, clock
