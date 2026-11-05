"""Pet Sales -> petstore-sales: reserve, buy, schedule the pickup, cancel.

The `Pet` aggregate owns reservation, purchase and status; the `PickupCalendar` owns the
shop's slots. The policy constants below drive the rules, the error texts and the
`pet-sales://policies` resource, so the three can't drift apart.
"""

import logging
import os
import re
import secrets
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from enum import StrEnum
from itertools import count, islice
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth import AuthProvider
from mcp_types import ToolAnnotations
from pydantic import BaseModel, Field
from starlette.requests import Request
from starlette.responses import JSONResponse

from petstore.events import (
    EventBus,
    PetBackOnOffer,
    PetPurchased,
    PetTakenOffOffer,
    PickupScheduled,
    PurchaseCancelled,
    Slot,
    clock_time,
)
from petstore.identity import Customer

# --- policies --------------------------------------------------------------------------------------

SHOP_TIMEZONE = ZoneInfo("America/Denver")  # the venue
OPENING_DAYS = range(0, 6)  # Mon–Sat
FIRST_SLOT = time(10)
LAST_SLOT = time(17)
SLOTS_LISTED = 6
DEFAULT_RESERVATION_HOLD = timedelta(hours=24)

DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
OPENING_HOURS = (
    f"hourly, {DAY_NAMES[OPENING_DAYS[0]]}–{DAY_NAMES[OPENING_DAYS[-1]]}, "
    f"{clock_time(FIRST_SLOT)} to {clock_time(LAST_SLOT)} (last slot)"
)


def describe_hold(hold: timedelta) -> str:
    seconds = int(hold.total_seconds())
    for unit, size in (("hour", 3600), ("minute", 60), ("second", 1)):
        if seconds % size == 0:
            amount = seconds // size
            return f"{amount} {unit}{'' if amount == 1 else 's'}"
    raise AssertionError("unreachable: every hold is a whole number of seconds")


# --- errors: the text starts with the error name, then says what to do next ---------------------------


class SalesError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(f"{type(self).__name__}: {message}")


class PetNotAvailable(SalesError):
    """Domain event *Purchase refused: pet not available*: sold, or reserved by someone else."""


class ReservationExpired(SalesError):
    """Domain event *Reservation expired*."""


class SlotNotAvailable(SalesError):
    """The slot is taken, outside opening hours or too soon."""

    @classmethod
    def listing(cls, problem: str, free_slots: list[datetime], next_action: str) -> "SlotNotAvailable":
        return cls(f"{problem}. Free slots: {list_slots(free_slots)}. {next_action}")


class TooLateToCancel(SalesError):
    """The pickup slot has come."""


class TooLateToReschedule(SalesError):
    """The pickup slot has come: moving it now would reopen cancelling."""


class UnknownPet(SalesError):
    """Technical error: nothing happened in the business."""


class UnknownPurchase(SalesError):
    """Technical error. Also another customer's purchase: its existence is not revealed."""


class UnknownReservation(SalesError):
    """Technical error: a reservation_id the customer doesn't hold for this pet."""


def list_slots(slots: list[datetime]) -> str:
    return ", ".join(f"{s.title} ({s.value})" for s in map(Slot.at, slots))


# --- clock -------------------------------------------------------------------------------------------


def shop_time(moment: datetime) -> datetime:
    """A naive time is shop time; an aware one is converted to it."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=SHOP_TIMEZONE)
    return moment.astimezone(SHOP_TIMEZONE)


class Clock:
    """The real clock, or a fixed one (PETSTORE_NOW) that the demo moves forward."""

    def __init__(self, fixed: datetime | None = None) -> None:
        self._fixed = shop_time(fixed) if fixed else None

    @classmethod
    def from_env(cls) -> "Clock":
        setting = os.environ.get("PETSTORE_NOW")
        return cls(fixed=datetime.fromisoformat(setting) if setting else None)

    def now(self) -> datetime:
        return self._fixed or datetime.now(SHOP_TIMEZONE)

    def advance(self, by: timedelta) -> None:
        if self._fixed is None:
            raise RuntimeError("The real clock can't be moved; set PETSTORE_NOW for a fixed one.")
        self._fixed += by


def reservation_hold_from_env() -> timedelta:
    setting = os.environ.get("RESERVATION_HOLD")
    if not setting:
        return DEFAULT_RESERVATION_HOLD
    match = re.fullmatch(r"(\d+)([hms])", setting.strip())
    if not match:
        raise ValueError(f"RESERVATION_HOLD={setting!r}: use a number with h, m or s, e.g. 24h")
    unit = {"h": "hours", "m": "minutes", "s": "seconds"}[match[2]]
    return timedelta(**{unit: int(match[1])})


# --- pickup calendar ---------------------------------------------------------------------------------


def earliest_pickup(now: datetime) -> datetime:
    return datetime.combine(now.date() + timedelta(days=1), time(0), tzinfo=SHOP_TIMEZONE)


def is_pickup_slot(moment: datetime) -> bool:
    on_the_hour = moment.minute == moment.second == moment.microsecond == 0
    return moment.weekday() in OPENING_DAYS and on_the_hour and FIRST_SLOT <= moment.time() <= LAST_SLOT


def slots_from(first_day: date) -> Iterator[datetime]:
    for offset in count():
        day = first_day + timedelta(days=offset)
        if day.weekday() in OPENING_DAYS:
            for hour in range(FIRST_SLOT.hour, LAST_SLOT.hour + 1):
                yield datetime.combine(day, time(hour), tzinfo=SHOP_TIMEZONE)


class PickupCalendar:
    """The shop's pickup slots: one pet per slot."""

    def __init__(self) -> None:
        self._taken: set[datetime] = set()

    def free_slots(self, now: datetime, count: int = SLOTS_LISTED) -> list[datetime]:
        free = (slot for slot in slots_from(earliest_pickup(now).date()) if slot not in self._taken)
        return list(islice(free, count))

    def validate(self, value: str, now: datetime, next_action: str) -> datetime:
        """The slot as shop time, or SlotNotAvailable listing the free slots and `next_action`."""
        free = self.free_slots(now)
        try:
            slot = shop_time(datetime.fromisoformat(value))
        except ValueError:
            example = Slot.at(free[0]).value
            raise SlotNotAvailable.listing(
                f"{value!r} is not a slot; pass a value like {example}", free, next_action
            ) from None
        problem = self._problem(slot, now)
        if problem:
            raise SlotNotAvailable.listing(f"{Slot.at(slot).title} {problem}", free, next_action)
        return slot

    def book(self, slot: datetime) -> None:
        self._taken.add(slot)

    def release(self, slot: datetime) -> None:
        self._taken.discard(slot)

    def _problem(self, slot: datetime, now: datetime) -> str | None:
        if not is_pickup_slot(slot):
            return f"is not a pickup slot ({OPENING_HOURS})"
        if slot < earliest_pickup(now):
            return "is too soon (pickup from the next day)"
        if slot in self._taken:
            return "was just taken"
        return None


# --- the Pet aggregate --------------------------------------------------------------------------------


class PetStatus(StrEnum):
    AVAILABLE = "available"
    RESERVED = "reserved"
    SOLD = "sold"


@dataclass
class Reservation:
    reservation_id: str
    customer: str
    pet_id: int
    expires: datetime


@dataclass
class Purchase:
    purchase_id: str
    customer: str
    pet_id: int
    purchased_at: datetime
    pickup: datetime | None = None


@dataclass
class Pet:
    pet_id: int
    name: str
    species: str
    tags: tuple[str, ...]
    status: PetStatus
    reservation: Reservation | None = None
    purchase: Purchase | None = None
    _expired: set[tuple[str, str]] = field(default_factory=set, repr=False)  # (customer, reservation_id)

    def reserve(self, customer: str, now: datetime, hold: timedelta, reservation_id: str) -> Reservation:
        """A second reservation by the same customer is the same reservation, not a new hold."""
        self._ensure_available_to(customer)
        if self.reservation is None:
            self.reservation = Reservation(reservation_id, customer, self.pet_id, expires=now + hold)
            self.status = PetStatus.RESERVED
        return self.reservation

    def expire_reservation(self, now: datetime) -> bool:
        if self.reservation is None or now < self.reservation.expires:
            return False
        self._expired.add((self.reservation.customer, self.reservation.reservation_id))
        self.reservation = None
        self.status = PetStatus.AVAILABLE
        return True

    def ensure_buyable_by(self, customer: str, reservation_id: str | None) -> None:
        if reservation_id is not None:
            self._check_reservation(customer, reservation_id)
        self._ensure_available_to(customer)

    def buy(self, customer: str, purchase_id: str, now: datetime, pickup: datetime | None) -> Purchase:
        """Buying uses up the customer's reservation, if there is one."""
        self._ensure_available_to(customer)
        self.purchase = Purchase(purchase_id, customer, self.pet_id, purchased_at=now, pickup=pickup)
        self.reservation = None
        self.status = PetStatus.SOLD
        return self.purchase

    def schedule_pickup(self, slot: datetime) -> None:
        assert self.purchase is not None
        self.purchase.pickup = slot

    def ensure_pickup_can_move(self, now: datetime) -> None:
        """Only until the slot; a purchase without a slot can get one any time."""
        self._ensure_before_pickup(now, TooLateToReschedule, "move the pickup")

    def cancel_purchase(self, now: datetime) -> Purchase:
        """Free until the pickup slot; without a slot, any time."""
        self._ensure_before_pickup(now, TooLateToCancel, "cancel")
        purchase = self.purchase
        assert purchase is not None
        self.purchase = None
        self.status = PetStatus.AVAILABLE
        return purchase

    def _ensure_before_pickup(self, now: datetime, refusal: type[SalesError], what: str) -> None:
        """The one rule for "the slot has passed": then the purchase is final."""
        assert self.purchase is not None
        pickup = self.purchase.pickup
        if pickup is not None and now >= pickup:
            raise refusal(
                f"{self.name} was due for pickup on {Slot.at(pickup).title}. Too late to {what}; contact the shop."
            )

    def _ensure_available_to(self, customer: str) -> None:
        if self.status is PetStatus.SOLD:
            raise PetNotAvailable(f"{self.name} is already sold. Use find_available_pets for others.")
        if self.reservation is not None and self.reservation.customer != customer:
            raise PetNotAvailable(f"{self.name} is reserved by someone else. Use find_available_pets for others.")

    def _check_reservation(self, customer: str, reservation_id: str) -> None:
        held = self.reservation
        if held is not None and (held.customer, held.reservation_id) == (customer, reservation_id):
            return
        if (customer, reservation_id) in self._expired:
            raise ReservationExpired(
                f"{self.name}'s reservation ran out. Reserve again with reserve_pet if {self.name} is still available."
            )
        raise UnknownReservation(
            f"No reservation {reservation_id} for {self.name}. "
            "Call buy_pet without reservation_id, or reserve_pet first."
        )


# --- the application service ---------------------------------------------------------------------------

BUY_WITH_ANOTHER_SLOT = "Call buy_pet again with one of them as pickup_slot."
SCHEDULE_ANOTHER_SLOT = "Call schedule_pickup with one of them."


def random_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(4)}"


def sequential_ids() -> Callable[[str], str]:
    """res-00000001, pur-00000001, ...: for the scripted demo, so its output is the same every run."""
    counters: Counter[str] = Counter()

    def new_id(prefix: str) -> str:
        counters[prefix] += 1
        return f"{prefix}-{counters[prefix]:08x}"

    return new_id


class PetSales:
    """Runs the use cases on the aggregate and publishes what happened. The customer is always given."""

    def __init__(
        self,
        pets: Iterable[Pet],
        bus: EventBus,
        clock: Clock,
        reservation_hold: timedelta = DEFAULT_RESERVATION_HOLD,
        new_id: Callable[[str], str] = random_id,
        pickup: bool = True,
    ) -> None:
        self._pets = {pet.pet_id: pet for pet in pets}
        self._bus = bus
        self._clock = clock
        self._hold = reservation_hold
        self._new_id = new_id
        self._pickup = pickup
        self._calendar = PickupCalendar()
        self._active_purchases: dict[str, int] = {}  # purchase_id -> pet_id

    def pet(self, pet_id: int) -> Pet:
        if pet_id not in self._pets:
            raise UnknownPet(f"No pet with id {pet_id}. Use find_available_pets to get ids.")
        return self._pets[pet_id]

    def now(self) -> datetime:
        return self._clock.now()

    @property
    def reservation_hold(self) -> timedelta:
        return self._hold

    @property
    def pickup(self) -> bool:
        """PICKUP=off: the original Petstore API's scope, no pickup calendar at all."""
        return self._pickup

    def reservation_held_by(self, customer: str, pet_id: int) -> Reservation | None:
        self.expire_reservations()
        reservation = self.pet(pet_id).reservation
        return reservation if reservation and reservation.customer == customer else None

    def reserve_pet(self, customer: str, pet_id: int) -> Reservation:
        self.expire_reservations()
        pet = self.pet(pet_id)
        was_on_offer = pet.status is PetStatus.AVAILABLE
        reservation = pet.reserve(customer, self.now(), self._hold, self._new_id("res"))
        if was_on_offer:
            self._bus.publish(PetTakenOffOffer(pet_id=pet_id))
        return reservation

    def buy_pet(
        self, customer: str, pet_id: int, pickup_slot: str | None = None, reservation_id: str | None = None
    ) -> Purchase:
        if pickup_slot:
            self._require_pickup()
        self.expire_reservations()
        pet = self.pet(pet_id)
        pet.ensure_buyable_by(customer, reservation_id)
        slot = self._calendar.validate(pickup_slot, self.now(), BUY_WITH_ANOTHER_SLOT) if pickup_slot else None
        was_on_offer = pet.status is PetStatus.AVAILABLE
        purchase = pet.buy(customer, self._new_id("pur"), self.now(), pickup=slot)
        if slot:
            self._calendar.book(slot)
        self._active_purchases[purchase.purchase_id] = pet_id
        if was_on_offer:
            self._bus.publish(PetTakenOffOffer(pet_id=pet_id))
        self._bus.publish(
            PetPurchased(
                purchase_id=purchase.purchase_id,
                customer=customer,
                pet_id=pet_id,
                pet_name=pet.name,
                species=pet.species,
                pickup_slot=Slot.at(slot) if slot else None,
                purchased_at=purchase.purchased_at,
            )
        )
        return purchase

    def schedule_pickup(self, customer: str, purchase_id: str, pickup_slot: str) -> Purchase:
        self._require_pickup()
        self.expire_reservations()
        pet, purchase = self._purchase_of(customer, purchase_id)
        pet.ensure_pickup_can_move(self.now())
        previous = purchase.pickup
        if previous:
            self._calendar.release(previous)
        try:
            slot = self._calendar.validate(pickup_slot, self.now(), SCHEDULE_ANOTHER_SLOT)
        except SlotNotAvailable:
            if previous:
                self._calendar.book(previous)
            raise
        pet.schedule_pickup(slot)
        self._calendar.book(slot)
        self._bus.publish(PickupScheduled(purchase_id=purchase_id, pickup_slot=Slot.at(slot)))
        return purchase

    def cancel_purchase(self, customer: str, purchase_id: str) -> Purchase:
        self.expire_reservations()
        pet, _ = self._purchase_of(customer, purchase_id)
        purchase = pet.cancel_purchase(self.now())
        if purchase.pickup:
            self._calendar.release(purchase.pickup)
        del self._active_purchases[purchase_id]
        self._bus.publish(PurchaseCancelled(purchase_id=purchase_id))
        self._bus.publish(PetBackOnOffer(pet_id=pet.pet_id))
        return purchase

    def expire_reservations(self) -> None:
        for pet in self._pets.values():
            if pet.expire_reservation(self.now()):
                self._bus.publish(PetBackOnOffer(pet_id=pet.pet_id))

    def free_slots(self) -> list[datetime]:
        return self._calendar.free_slots(self.now())

    def stock(self) -> dict[str, int]:
        self.expire_reservations()
        counts = Counter(pet.status for pet in self._pets.values())
        return {status.value: counts[status] for status in PetStatus}

    def policies(self) -> str:
        hold = describe_hold(self._hold)
        lines = [
            "# Pet Sales policies\n",
            f"- **Reservation** (optional): holds the pet for {hold}, then it is back on offer.",
            "- **Buying**: with or without a reservation.",
        ]
        if self._pickup:
            lines += [
                f"- **Pickup**: in the shop, in an offered slot: {OPENING_HOURS}, from the next day, "
                f"one pet per slot (shop time, {SHOP_TIMEZONE.key}); can be moved until its slot.",
                "- **Cancelling**: free until the pickup slot; without a slot, any time. The pet goes back on offer.",
            ]
        else:
            lines.append("- **Cancelling**: free, any time. The pet goes back on offer.")
        return "\n".join(lines) + "\n"

    def _require_pickup(self) -> None:
        if not self._pickup:
            raise ValueError("No pickup in this shop (PICKUP=off): no pickup slots to give.")

    def _purchase_of(self, customer: str, purchase_id: str) -> tuple[Pet, Purchase]:
        pet_id = self._active_purchases.get(purchase_id)
        purchase = self._pets[pet_id].purchase if pet_id is not None else None
        if purchase is None or purchase.customer != customer:
            raise UnknownPurchase(f"No purchase with id {purchase_id}. Use my_purchases to see yours.")
        return self._pets[purchase.pet_id], purchase


# --- petstore-sales: the MCP surface -----------------------------------------------------------------

INSTRUCTIONS = "Pet Sales: reserve and buy pets for the signed-in customer and schedule or cancel the pickup."
INSTRUCTIONS_WITHOUT_PICKUP = "Pet Sales: reserve, buy and cancel purchases of pets for the signed-in customer."

ADDITIVE_WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False)


class ReservationResult(BaseModel):
    reservation_id: str
    pet_id: int
    pet: str
    expires: Slot
    next_step: str


class PurchaseResult(BaseModel):
    purchase_id: str
    pet_id: int
    pet: str
    next_step: str


class PurchaseWithPickupResult(PurchaseResult):
    pickup: Slot | None
    free_slots: list[Slot] | None = Field(default=None, exclude_if=lambda slots: slots is None)


class PickupResult(BaseModel):
    purchase_id: str
    pet: str
    pickup: Slot
    next_step: str


class CancellationResult(BaseModel):
    purchase_id: str
    pet: str
    status: Literal["cancelled"] = "cancelled"
    next_step: str


PetId = Annotated[int, Field(description="From find_available_pets.")]
PurchaseId = Annotated[str, Field(description="From buy_pet or my_purchases.")]
PickupSlotValue = Annotated[str, Field(description="A slot value such as 2026-11-10T10:00, from a result.")]
ReservationId = Annotated[str | None, Field(description="Optional check, from reserve_pet.")]


@contextmanager
def tool_errors() -> Iterator[None]:
    """Domain refusals become MCP results with isError and the error's text.

    Logged at INFO: a refusal is the business working as intended, not a server error.
    """
    try:
        yield
    except SalesError as error:
        raise ToolError(str(error), log_level=logging.INFO) from error


def reservation_result(sales: PetSales, reservation: Reservation, already_held: bool) -> ReservationResult:
    pet = sales.pet(reservation.pet_id)
    expires = Slot.at(reservation.expires)
    held = "already reserved for you" if already_held else "reserved for you"
    return ReservationResult(
        reservation_id=reservation.reservation_id,
        pet_id=pet.pet_id,
        pet=pet.name,
        expires=expires,
        next_step=f"{pet.name} is {held} until {expires.title}. To buy, call buy_pet with pet_id {pet.pet_id}.",
    )


def purchase_with_pickup_result(sales: PetSales, purchase: Purchase) -> PurchaseWithPickupResult:
    pet = sales.pet(purchase.pet_id)
    if purchase.pickup:
        pickup = Slot.at(purchase.pickup)
        return PurchaseWithPickupResult(
            purchase_id=purchase.purchase_id,
            pet_id=pet.pet_id,
            pet=pet.name,
            pickup=pickup,
            next_step=f"{pet.name} is yours. Pickup at the shop on {pickup.title}.",
        )
    free = sales.free_slots()
    return PurchaseWithPickupResult(
        purchase_id=purchase.purchase_id,
        pet_id=pet.pet_id,
        pet=pet.name,
        pickup=None,
        free_slots=[Slot.at(slot) for slot in free],
        next_step=(
            f"{pet.name} is yours. Pickup not scheduled yet. Free slots: {list_slots(free)}. "
            "Ask the customer, then call schedule_pickup."
        ),
    )


def create_server(sales: PetSales, auth: AuthProvider | None = None) -> FastMCP:
    """With PICKUP=off: no schedule_pickup, no pickup_slot, no pickup in results or policies."""
    instructions = INSTRUCTIONS if sales.pickup else INSTRUCTIONS_WITHOUT_PICKUP
    server = FastMCP("petstore-sales", instructions=instructions, auth=auth)
    _add_reserve_pet(server, sales)
    if sales.pickup:
        _add_buy_pet_with_pickup(server, sales)
        _add_schedule_pickup(server, sales)
    else:
        _add_buy_pet(server, sales)
    _add_cancel_purchase(server, sales)
    _add_policies(server, sales)
    _add_stock(server, sales)
    return server


def _add_reserve_pet(server: FastMCP, sales: PetSales) -> None:
    @server.tool(
        title="Reserve a pet",
        description=(
            f"Hold a pet for the customer for {describe_hold(sales.reservation_hold)} while they decide. "
            "Optional: buy_pet works without a reservation."
        ),
        annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, idempotent_hint=True),
    )
    def reserve_pet(pet_id: PetId, customer: str = Customer()) -> ReservationResult:
        with tool_errors():
            already_held = sales.reservation_held_by(customer, pet_id) is not None
            return reservation_result(sales, sales.reserve_pet(customer, pet_id), already_held)


def _add_buy_pet_with_pickup(server: FastMCP, sales: PetSales) -> None:
    @server.tool(title="Buy a pet", annotations=ADDITIVE_WRITE)
    def buy_pet(
        pet_id: PetId,
        pickup_slot: Annotated[
            str | None, Field(description="Only if the customer already chose a slot, e.g. 2026-11-10T10:00.")
        ] = None,
        reservation_id: ReservationId = None,
        customer: str = Customer(),
    ) -> PurchaseWithPickupResult:
        """Buy a pet for the customer. Without pickup_slot, the result lists the free pickup slots."""
        with tool_errors():
            return purchase_with_pickup_result(sales, sales.buy_pet(customer, pet_id, pickup_slot, reservation_id))


def _add_buy_pet(server: FastMCP, sales: PetSales) -> None:
    @server.tool(title="Buy a pet", annotations=ADDITIVE_WRITE)
    def buy_pet(pet_id: PetId, reservation_id: ReservationId = None, customer: str = Customer()) -> PurchaseResult:
        """Buy a pet for the customer."""
        with tool_errors():
            purchase = sales.buy_pet(customer, pet_id, reservation_id=reservation_id)
        pet = sales.pet(pet_id).name
        return PurchaseResult(purchase_id=purchase.purchase_id, pet_id=pet_id, pet=pet, next_step=f"{pet} is yours.")


def _add_schedule_pickup(server: FastMCP, sales: PetSales) -> None:
    @server.tool(title="Schedule the pickup", annotations=ADDITIVE_WRITE)
    def schedule_pickup(
        purchase_id: PurchaseId, pickup_slot: PickupSlotValue, customer: str = Customer()
    ) -> PickupResult:
        """Schedule or change when the customer picks up a purchased pet at the shop."""
        with tool_errors():
            purchase = sales.schedule_pickup(customer, purchase_id, pickup_slot)
        pet = sales.pet(purchase.pet_id).name
        pickup = Slot.at(purchase.pickup)
        return PickupResult(
            purchase_id=purchase_id,
            pet=pet,
            pickup=pickup,
            next_step=f"Pickup scheduled: {pet} at the shop on {pickup.title}. Free to cancel until then.",
        )


def _add_cancel_purchase(server: FastMCP, sales: PetSales) -> None:
    when = "free until the pickup slot" if sales.pickup else "free, any time"

    @server.tool(
        title="Cancel a purchase",
        description=f"Cancel a purchase: {when}. The pet goes back on offer.",
        annotations=ToolAnnotations(read_only_hint=False, destructive_hint=True),
    )
    def cancel_purchase(purchase_id: PurchaseId, customer: str = Customer()) -> CancellationResult:
        with tool_errors():
            purchase = sales.cancel_purchase(customer, purchase_id)
        pet = sales.pet(purchase.pet_id).name
        return CancellationResult(
            purchase_id=purchase_id, pet=pet, next_step=f"Purchase cancelled; {pet} is back on offer."
        )


def _add_policies(server: FastMCP, sales: PetSales) -> None:
    what = "Reservation, pickup and cancellation rules." if sales.pickup else "Reservation and cancellation rules."

    @server.resource(
        "pet-sales://policies", name="policies", title="Pet Sales policies", description=what, mime_type="text/markdown"
    )
    def policies() -> str:
        return sales.policies()


def _add_stock(server: FastMCP, sales: PetSales) -> None:
    # REST for the shop's dashboard, not a tool: buyers never need it. Custom routes are not covered
    # by FastMCP auth, so it is open in the demo; in production it would check a shop-staff role.
    @server.custom_route("/stock", methods=["GET"])
    async def stock(request: Request) -> JSONResponse:
        return JSONResponse(sales.stock())
