import re
from datetime import timedelta

import pytest

from petstore.events import PetBackOnOffer, PetPurchased, PetTakenOffOffer, PickupScheduled, PurchaseCancelled, Slot
from petstore.sales import (
    PetNotAvailable,
    PetStatus,
    ReservationExpired,
    SlotNotAvailable,
    TooLateToCancel,
    TooLateToReschedule,
    UnknownPet,
    UnknownPurchase,
    UnknownReservation,
)
from tests.factories import TALK, pet_sales

TUESDAY_10 = "2026-11-10T10:00"


# --- reserve -----------------------------------------------------------------------------------------


def test_a_reservation_holds_the_pet_for_24_hours() -> None:
    sales, bus, _ = pet_sales()
    reservation = sales.reserve_pet("alice", 1)
    assert re.fullmatch(r"res-[0-9a-f]{8}", reservation.reservation_id)
    assert reservation.expires == TALK + timedelta(hours=24)
    assert sales.pet(1).status is PetStatus.RESERVED
    assert bus.published == [PetTakenOffOffer(pet_id=1)]


def test_reserving_again_gives_the_customer_the_same_reservation() -> None:
    sales, bus, clock = pet_sales()
    first = sales.reserve_pet("alice", 1)
    clock.advance(timedelta(hours=1))
    again = sales.reserve_pet("alice", 1)
    assert again == first
    assert bus.published == [PetTakenOffOffer(pet_id=1)]


def test_a_pet_reserved_by_someone_else_cannot_be_reserved() -> None:
    sales, _, _ = pet_sales()
    sales.reserve_pet("alice", 1)
    with pytest.raises(PetNotAvailable, match="^PetNotAvailable: Rex is reserved by someone else."):
        sales.reserve_pet("bob", 1)


def test_a_sold_pet_cannot_be_reserved() -> None:
    sales, _, _ = pet_sales()
    with pytest.raises(PetNotAvailable, match="^PetNotAvailable: Max is already sold. Use find_available_pets"):
        sales.reserve_pet("alice", 4)


def test_an_unknown_pet_cannot_be_reserved() -> None:
    sales, _, _ = pet_sales()
    with pytest.raises(UnknownPet) as refused:
        sales.reserve_pet("alice", 7)
    assert str(refused.value) == "UnknownPet: No pet with id 7. Use find_available_pets to get ids."


def test_a_reservation_expires_after_the_hold_and_the_pet_is_back_on_offer() -> None:
    sales, bus, clock = pet_sales()
    sales.reserve_pet("alice", 3)
    clock.advance(timedelta(hours=24))
    sales.expire_reservations()
    assert sales.pet(3).status is PetStatus.AVAILABLE
    assert bus.published[-1] == PetBackOnOffer(pet_id=3)


def test_a_reservation_is_still_held_just_before_it_expires() -> None:
    sales, _, clock = pet_sales()
    sales.reserve_pet("alice", 3)
    clock.advance(timedelta(hours=24) - timedelta(seconds=1))
    sales.expire_reservations()
    assert sales.pet(3).status is PetStatus.RESERVED


def test_every_pet_sales_call_checks_expiry_first() -> None:
    sales, _, clock = pet_sales()
    sales.reserve_pet("alice", 3)
    clock.advance(timedelta(hours=25))
    assert sales.reserve_pet("bob", 3).customer == "bob"


def test_the_hold_is_configurable() -> None:
    sales, _, _ = pet_sales(hold=timedelta(minutes=5))
    assert sales.reserve_pet("alice", 1).expires == TALK + timedelta(minutes=5)


# --- buy -------------------------------------------------------------------------------------------


def test_a_pet_can_be_bought_without_a_reservation_or_a_slot() -> None:
    sales, bus, _ = pet_sales()
    purchase = sales.buy_pet("alice", 1)
    assert re.fullmatch(r"pur-[0-9a-f]{8}", purchase.purchase_id)
    assert purchase.pickup is None
    assert sales.pet(1).status is PetStatus.SOLD
    assert bus.published == [
        PetTakenOffOffer(pet_id=1),
        PetPurchased(
            purchase_id=purchase.purchase_id,
            customer="alice",
            pet_id=1,
            pet_name="Rex",
            species="dog",
            pickup_slot=None,
            purchased_at=TALK,
        ),
    ]


def test_buying_with_a_slot_schedules_the_pickup_in_one_call() -> None:
    sales, bus, _ = pet_sales()
    purchase = sales.buy_pet("alice", 1, pickup_slot=TUESDAY_10)
    assert Slot.at(purchase.pickup) == Slot(value=TUESDAY_10, title="Tue, Nov 10, 10:00 AM")
    assert bus.published[-1].pickup_slot == Slot.at(purchase.pickup)
    assert TUESDAY_10 not in [Slot.at(s).value for s in sales.free_slots()]


def test_the_customer_holding_the_reservation_can_buy_without_its_id() -> None:
    sales, bus, _ = pet_sales()
    sales.reserve_pet("alice", 1)
    sales.buy_pet("alice", 1)
    assert sales.pet(1).status is PetStatus.SOLD
    assert sales.pet(1).reservation is None
    assert [type(e) for e in bus.published] == [PetTakenOffOffer, PetPurchased]


def test_the_reservation_id_is_checked_when_given() -> None:
    sales, _, _ = pet_sales()
    reservation = sales.reserve_pet("alice", 1)
    assert sales.buy_pet("alice", 1, reservation_id=reservation.reservation_id).pet_id == 1


def test_an_expired_reservation_is_refused() -> None:
    sales, _, clock = pet_sales()
    reservation = sales.reserve_pet("alice", 3)
    clock.advance(timedelta(hours=25))
    with pytest.raises(ReservationExpired) as refused:
        sales.buy_pet("alice", 3, reservation_id=reservation.reservation_id)
    assert str(refused.value) == (
        "ReservationExpired: Bello's reservation ran out. Reserve again with reserve_pet if Bello is still available."
    )
    assert sales.pet(3).status is PetStatus.AVAILABLE


@pytest.mark.parametrize("reservation_id", ["res-00000000", "made-up"])
def test_a_reservation_id_the_customer_does_not_hold_is_refused(reservation_id: str) -> None:
    sales, _, _ = pet_sales()
    with pytest.raises(UnknownReservation, match=f"^UnknownReservation: No reservation {reservation_id} for Rex"):
        sales.buy_pet("alice", 1, reservation_id=reservation_id)


def test_someone_elses_reservation_id_is_unknown_to_the_customer() -> None:
    sales, _, _ = pet_sales()
    reservation = sales.reserve_pet("alice", 1)
    with pytest.raises(UnknownReservation):
        sales.buy_pet("bob", 1, reservation_id=reservation.reservation_id)


def test_a_sold_pet_cannot_be_bought() -> None:
    sales, _, _ = pet_sales()
    with pytest.raises(PetNotAvailable) as refused:
        sales.buy_pet("bob", 4)
    assert str(refused.value) == "PetNotAvailable: Max is already sold. Use find_available_pets for others."


def test_a_pet_bought_by_one_customer_is_refused_to_the_next() -> None:
    sales, _, _ = pet_sales()
    sales.buy_pet("alice", 1)
    with pytest.raises(PetNotAvailable, match="^PetNotAvailable: Rex is already sold."):
        sales.buy_pet("bob", 1)


def test_a_pet_reserved_by_someone_else_cannot_be_bought() -> None:
    sales, _, _ = pet_sales()
    sales.reserve_pet("alice", 1)
    with pytest.raises(PetNotAvailable, match="^PetNotAvailable: Rex is reserved by someone else."):
        sales.buy_pet("bob", 1)


def test_an_unknown_pet_cannot_be_bought() -> None:
    sales, _, _ = pet_sales()
    with pytest.raises(UnknownPet):
        sales.buy_pet("alice", 7)


def test_a_purchase_with_a_slot_that_is_not_free_does_not_happen() -> None:
    sales, bus, _ = pet_sales()
    sales.buy_pet("alice", 1, pickup_slot=TUESDAY_10)
    with pytest.raises(SlotNotAvailable, match=r"Call buy_pet again with one of them as pickup_slot\.$"):
        sales.buy_pet("bob", 3, pickup_slot=TUESDAY_10)
    assert sales.pet(3).status is PetStatus.AVAILABLE
    assert len(bus.published) == 2


def test_the_pet_error_comes_before_the_slot_error() -> None:
    sales, _, _ = pet_sales()
    with pytest.raises(PetNotAvailable):
        sales.buy_pet("alice", 4, pickup_slot="not a slot")


# --- schedule the pickup ------------------------------------------------------------------------------


def test_the_pickup_can_be_scheduled_after_the_purchase() -> None:
    sales, bus, _ = pet_sales()
    purchase = sales.buy_pet("alice", 1)
    scheduled = sales.schedule_pickup("alice", purchase.purchase_id, TUESDAY_10)
    assert Slot.at(scheduled.pickup).value == TUESDAY_10
    assert bus.published[-1] == PickupScheduled(
        purchase_id=purchase.purchase_id, pickup_slot=Slot(value=TUESDAY_10, title="Tue, Nov 10, 10:00 AM")
    )


def test_rescheduling_frees_the_old_slot() -> None:
    sales, _, _ = pet_sales()
    purchase = sales.buy_pet("alice", 1, pickup_slot=TUESDAY_10)
    sales.schedule_pickup("alice", purchase.purchase_id, "2026-11-10T11:00")
    assert Slot.at(sales.free_slots()[0]).value == TUESDAY_10


def test_a_taken_slot_cannot_be_scheduled() -> None:
    sales, _, _ = pet_sales()
    sales.buy_pet("alice", 1, pickup_slot=TUESDAY_10)
    purchase = sales.buy_pet("bob", 3)
    with pytest.raises(SlotNotAvailable, match=r"was just taken.*Call schedule_pickup with one of them\.$"):
        sales.schedule_pickup("bob", purchase.purchase_id, TUESDAY_10)


def test_someone_elses_purchase_is_unknown_when_scheduling() -> None:
    sales, _, _ = pet_sales()
    purchase = sales.buy_pet("alice", 1)
    with pytest.raises(UnknownPurchase) as refused:
        sales.schedule_pickup("bob", purchase.purchase_id, TUESDAY_10)
    assert str(refused.value) == (
        f"UnknownPurchase: No purchase with id {purchase.purchase_id}. Use my_purchases to see yours."
    )


# --- cancel --------------------------------------------------------------------------------------------


def test_a_purchase_without_a_slot_can_be_cancelled_any_time() -> None:
    sales, bus, clock = pet_sales()
    purchase = sales.buy_pet("alice", 1)
    clock.advance(timedelta(days=30))
    cancelled = sales.cancel_purchase("alice", purchase.purchase_id)
    assert cancelled.purchase_id == purchase.purchase_id
    assert sales.pet(1).status is PetStatus.AVAILABLE
    assert bus.published[-2:] == [PurchaseCancelled(purchase_id=purchase.purchase_id), PetBackOnOffer(pet_id=1)]


def test_a_purchase_can_be_cancelled_until_the_slot() -> None:
    sales, _, clock = pet_sales()
    purchase = sales.buy_pet("alice", 1, pickup_slot=TUESDAY_10)
    clock.advance(timedelta(hours=17, minutes=14))  # Tue 9:59 AM
    sales.cancel_purchase("alice", purchase.purchase_id)
    assert sales.pet(1).status is PetStatus.AVAILABLE


def test_a_cancelled_slot_can_be_booked_again() -> None:
    sales, _, _ = pet_sales()
    purchase = sales.buy_pet("alice", 1, pickup_slot=TUESDAY_10)
    sales.cancel_purchase("alice", purchase.purchase_id)
    assert sales.buy_pet("bob", 3, pickup_slot=TUESDAY_10).pet_id == 3


def test_it_is_too_late_to_cancel_once_the_slot_has_come() -> None:
    sales, _, clock = pet_sales()
    purchase = sales.buy_pet("alice", 1, pickup_slot=TUESDAY_10)
    clock.advance(timedelta(hours=17, minutes=15))  # Tue 10:00 AM
    with pytest.raises(TooLateToCancel) as refused:
        sales.cancel_purchase("alice", purchase.purchase_id)
    assert str(refused.value) == (
        "TooLateToCancel: Rex was due for pickup on Tue, Nov 10, 10:00 AM. Too late to cancel; contact the shop."
    )
    assert sales.pet(1).status is PetStatus.SOLD


def test_a_pickup_can_be_moved_until_its_slot() -> None:
    sales, _, clock = pet_sales()
    purchase = sales.buy_pet("alice", 1, pickup_slot=TUESDAY_10)
    clock.advance(timedelta(hours=17, minutes=14))  # Tue 9:59 AM
    assert sales.schedule_pickup("alice", purchase.purchase_id, "2026-11-11T10:00").pickup.day == 11


def test_it_is_too_late_to_move_the_pickup_once_the_slot_has_come() -> None:
    sales, bus, clock = pet_sales()
    purchase = sales.buy_pet("alice", 1, pickup_slot=TUESDAY_10)
    clock.advance(timedelta(hours=17, minutes=15))  # Tue 10:00 AM
    published = len(bus.published)
    with pytest.raises(TooLateToReschedule) as refused:
        sales.schedule_pickup("alice", purchase.purchase_id, "2026-11-11T10:00")
    assert str(refused.value) == (
        "TooLateToReschedule: Rex was due for pickup on Tue, Nov 10, 10:00 AM. "
        "Too late to move the pickup; contact the shop."
    )
    assert purchase.pickup.day == 10 and len(bus.published) == published


def test_moving_a_passed_pickup_cannot_open_a_way_to_cancel() -> None:
    sales, _, clock = pet_sales()
    purchase = sales.buy_pet("alice", 1, pickup_slot=TUESDAY_10)
    clock.advance(timedelta(days=1))
    with pytest.raises(TooLateToReschedule):
        sales.schedule_pickup("alice", purchase.purchase_id, "2026-11-12T10:00")
    with pytest.raises(TooLateToCancel):
        sales.cancel_purchase("alice", purchase.purchase_id)
    assert sales.pet(1).status is PetStatus.SOLD


def test_a_purchase_without_a_slot_can_get_one_any_time() -> None:
    sales, _, clock = pet_sales()
    purchase = sales.buy_pet("alice", 1)
    clock.advance(timedelta(days=3))
    assert sales.schedule_pickup("alice", purchase.purchase_id, "2026-11-13T10:00").pickup.day == 13


def test_someone_elses_purchase_is_unknown_when_cancelling() -> None:
    sales, _, _ = pet_sales()
    purchase = sales.buy_pet("alice", 1)
    with pytest.raises(UnknownPurchase):
        sales.cancel_purchase("bob", purchase.purchase_id)
    assert sales.pet(1).status is PetStatus.SOLD


def test_a_cancelled_purchase_cannot_be_cancelled_again() -> None:
    sales, _, _ = pet_sales()
    purchase = sales.buy_pet("alice", 1)
    sales.cancel_purchase("alice", purchase.purchase_id)
    with pytest.raises(UnknownPurchase):
        sales.cancel_purchase("alice", purchase.purchase_id)


def test_a_cancelled_pet_can_be_bought_again() -> None:
    sales, _, _ = pet_sales()
    sales.cancel_purchase("alice", sales.buy_pet("alice", 1).purchase_id)
    assert sales.buy_pet("bob", 1).customer == "bob"


# --- stock and policies -----------------------------------------------------------------------------


def test_the_stock_counts_pets_by_status() -> None:
    sales, _, _ = pet_sales()
    sales.reserve_pet("alice", 1)
    assert sales.stock() == {"available": 2, "reserved": 1, "sold": 1}


def test_the_policies_are_written_from_the_same_rules() -> None:
    sales, _, _ = pet_sales(hold=timedelta(hours=2))
    policies = sales.policies()
    assert "holds the pet for 2 hours" in policies
    assert "Mon–Sat, 10:00 AM to 5:00 PM (last slot)" in policies
    assert "from the next day" in policies
    assert "free until the pickup slot" in policies


# --- PICKUP=off: the same scope as the original Petstore API -------------------------------------------


def test_without_pickup_a_purchase_has_no_slot_and_can_be_cancelled_any_time() -> None:
    sales, bus, clock = pet_sales(pickup=False)
    purchase = sales.buy_pet("alice", 1)
    assert purchase.pickup is None and bus.published[-1].pickup_slot is None
    clock.advance(timedelta(days=30))
    sales.cancel_purchase("alice", purchase.purchase_id)
    assert sales.pet(1).status is PetStatus.AVAILABLE


def test_without_pickup_a_slot_cannot_be_given() -> None:
    sales, _, _ = pet_sales(pickup=False)
    with pytest.raises(ValueError, match="PICKUP=off"):
        sales.buy_pet("alice", 1, pickup_slot=TUESDAY_10)
    purchase = sales.buy_pet("alice", 1)
    with pytest.raises(ValueError, match="PICKUP=off"):
        sales.schedule_pickup("alice", purchase.purchase_id, TUESDAY_10)


def test_without_pickup_the_policies_have_no_pickup_lines() -> None:
    sales, _, _ = pet_sales(pickup=False)
    policies = sales.policies()
    assert "pickup" not in policies.lower() and "slot" not in policies.lower()
    assert "- **Cancelling**: free, any time. The pet goes back on offer." in policies
    assert "holds the pet for 24 hours" in policies


def test_the_policies_say_the_pickup_can_be_moved_until_its_slot() -> None:
    sales, _, _ = pet_sales()
    assert "can be moved until its slot" in sales.policies()
