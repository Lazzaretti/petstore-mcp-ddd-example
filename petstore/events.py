"""Events between the contexts and the bus that carries them (shared infrastructure).

Pet Sales publishes; Pet Discovery and Pet Handover subscribe. The event types and `Slot`
are the published language: the only things the contexts share.
"""

import os
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time

from pydantic import BaseModel, ConfigDict


def clock_time(moment: datetime | time) -> str:
    """US 12-hour clock: 10:00 AM, 4:45 PM, 12:00 PM."""
    hour = moment.hour % 12 or 12
    return f"{hour}:{moment.minute:02d} {'AM' if moment.hour < 12 else 'PM'}"


class Slot(BaseModel):
    """A point in shop time: `value` is what the agent passes, `title` what people read."""

    model_config = ConfigDict(frozen=True)

    value: str
    title: str

    @classmethod
    def at(cls, moment: datetime) -> "Slot":
        return cls(value=f"{moment:%Y-%m-%dT%H:%M}", title=f"{moment:%a, %b} {moment.day}, {clock_time(moment)}")


@dataclass(frozen=True)
class PetTakenOffOffer:
    pet_id: int


@dataclass(frozen=True)
class PetBackOnOffer:
    pet_id: int


@dataclass(frozen=True)
class PetPurchased:
    purchase_id: str
    customer: str
    pet_id: int
    pet_name: str
    species: str
    pickup_slot: Slot | None
    purchased_at: datetime


@dataclass(frozen=True)
class PickupScheduled:
    purchase_id: str
    pickup_slot: Slot


@dataclass(frozen=True)
class PurchaseCancelled:
    purchase_id: str


type Event = PetTakenOffOffer | PetBackOnOffer | PetPurchased | PickupScheduled | PurchaseCancelled


class EventBus:
    """In memory and synchronous: handlers run before `publish` returns, so a read after a write is consistent."""

    def __init__(self) -> None:
        self._handlers: defaultdict[type, list[Callable]] = defaultdict(list)

    def subscribe[E](self, event_type: type[E], handler: Callable[[E], None]) -> None:
        self._handlers[event_type].append(handler)

    def publish(self, event: Event) -> None:
        for handler in self._handlers[type(event)]:
            handler(event)


def create_bus() -> EventBus:
    if os.environ.get("EVENT_BUS", "memory") != "memory":
        raise NotImplementedError("Only EVENT_BUS=memory is built; NATS is the kmcp stretch goal.")
    return EventBus()
