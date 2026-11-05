from petstore.discovery import PetDiscovery, PetOffer
from petstore.events import EventBus, PetBackOnOffer, PetTakenOffOffer


def pet_discovery() -> tuple[PetDiscovery, EventBus]:
    bus = EventBus()
    offers = [
        PetOffer(1, "Rex", "dog", ("friendly",), on_offer=True),
        PetOffer(2, "Mia", "cat", ("indoor",), on_offer=True),
        PetOffer(3, "Bello", "dog", ("puppy", "friendly"), on_offer=True),
        PetOffer(4, "Max", "dog", ("friendly",), on_offer=False),
    ]
    return PetDiscovery(offers, bus), bus


def names(offers: list[PetOffer]) -> list[str]:
    return [offer.name for offer in offers]


def test_only_pets_on_offer_are_found() -> None:
    discovery, _ = pet_discovery()
    assert names(discovery.find_available_pets()) == ["Rex", "Mia", "Bello"]


def test_pets_are_found_by_species_and_tag_in_any_case() -> None:
    discovery, _ = pet_discovery()
    assert names(discovery.find_available_pets(species="Dog", tag="FRIENDLY")) == ["Rex", "Bello"]
    assert names(discovery.find_available_pets(tag="indoor")) == ["Mia"]
    assert names(discovery.find_available_pets(species="fish")) == []


def test_a_pet_taken_off_offer_is_no_longer_found() -> None:
    discovery, bus = pet_discovery()
    bus.publish(PetTakenOffOffer(pet_id=1))
    assert names(discovery.find_available_pets(species="dog")) == ["Bello"]


def test_a_pet_back_on_offer_is_found_again() -> None:
    discovery, bus = pet_discovery()
    bus.publish(PetTakenOffOffer(pet_id=1))
    bus.publish(PetBackOnOffer(pet_id=1))
    assert names(discovery.find_available_pets(species="dog")) == ["Rex", "Bello"]
