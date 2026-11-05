from petstore.events import EventBus, PetPurchased, PickupScheduled, PurchaseCancelled, Slot
from petstore.handover import PetHandover, PurchaseView
from tests.factories import TALK

TUESDAY_10 = Slot(value="2026-11-10T10:00", title="Tue, Nov 10, 10:00 AM")


def purchased(purchase_id: str, customer: str, pickup_slot: Slot | None = None) -> PetPurchased:
    return PetPurchased(purchase_id, customer, 1, "Rex", "dog", pickup_slot, purchased_at=TALK)


def pet_handover() -> tuple[PetHandover, EventBus]:
    bus = EventBus()
    return PetHandover(bus), bus


def test_a_purchase_shows_up_for_its_customer_only() -> None:
    handover, bus = pet_handover()
    bus.publish(purchased("pur-1", "alice", TUESDAY_10))
    assert handover.purchases_of("alice") == [PurchaseView("pur-1", "alice", "Rex", TUESDAY_10)]
    assert handover.purchases_of("bob") == []


def test_a_scheduled_pickup_updates_the_purchase() -> None:
    handover, bus = pet_handover()
    bus.publish(purchased("pur-1", "alice"))
    bus.publish(PickupScheduled("pur-1", TUESDAY_10))
    assert handover.purchases_of("alice")[0].pickup == TUESDAY_10


def test_a_cancelled_purchase_is_dropped() -> None:
    handover, bus = pet_handover()
    bus.publish(purchased("pur-1", "alice"))
    bus.publish(PurchaseCancelled("pur-1"))
    assert handover.purchases_of("alice") == []


def test_purchases_are_listed_in_the_order_they_were_made() -> None:
    handover, bus = pet_handover()
    bus.publish(purchased("pur-2", "alice"))
    bus.publish(purchased("pur-1", "alice"))
    assert [p.purchase_id for p in handover.purchases_of("alice")] == ["pur-2", "pur-1"]
