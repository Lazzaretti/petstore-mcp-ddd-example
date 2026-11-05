"""Events between the contexts: Pet Sales publishes, Pet Discovery and Pet Handover follow."""

from datetime import timedelta

from petstore.app import create_petstore
from tests.factories import TALK


def test_a_purchase_takes_the_pet_off_offer_and_shows_up_in_pet_handover() -> None:
    petstore = create_petstore(now=TALK)
    purchase = petstore.sales.buy_pet("alice", 1, pickup_slot="2026-11-10T10:00")
    assert [o.name for o in petstore.discovery.find_available_pets(species="dog")] == ["Bello"]
    [view] = petstore.handover.purchases_of("alice")
    assert (view.purchase_id, view.pet, view.pickup.title) == (purchase.purchase_id, "Rex", "Tue, Nov 10, 10:00 AM")


def test_a_cancelled_purchase_puts_the_pet_back_and_leaves_pet_handover() -> None:
    petstore = create_petstore(now=TALK)
    purchase = petstore.sales.buy_pet("alice", 1)
    petstore.sales.cancel_purchase("alice", purchase.purchase_id)
    assert "Rex" in [o.name for o in petstore.discovery.find_available_pets()]
    assert petstore.handover.purchases_of("alice") == []


def test_an_expired_reservation_puts_the_pet_back_on_offer() -> None:
    petstore = create_petstore(now=TALK)
    petstore.sales.reserve_pet("alice", 3)
    assert "Bello" not in [o.name for o in petstore.discovery.find_available_pets()]
    petstore.clock.advance(timedelta(hours=25))
    petstore.sales.expire_reservations()
    assert "Bello" in [o.name for o in petstore.discovery.find_available_pets()]


def test_the_seed_has_a_sold_pet_that_pet_discovery_never_shows() -> None:
    petstore = create_petstore(now=TALK)
    assert [o.name for o in petstore.discovery.find_available_pets()] == ["Rex", "Mia", "Bello"]
    assert petstore.sales.stock() == {"available": 3, "reserved": 0, "sold": 1}
