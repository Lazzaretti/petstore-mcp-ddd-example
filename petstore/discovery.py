"""Pet Discovery -> petstore-discovery: which pets are on offer.

A read model fed by Pet Sales' events: a pet leaves the offer when it is reserved or
bought and comes back when a purchase is cancelled or a reservation runs out.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.server.auth import AuthProvider
from mcp_types import ToolAnnotations
from pydantic import BaseModel, Field

from petstore.events import EventBus, PetBackOnOffer, PetTakenOffOffer

INSTRUCTIONS = "Pet Discovery: find the pets the shop has on offer."


@dataclass
class PetOffer:
    pet_id: int
    name: str
    species: str
    tags: tuple[str, ...]
    on_offer: bool


class PetDiscovery:
    def __init__(self, offers: Iterable[PetOffer], bus: EventBus) -> None:
        self._offers = {offer.pet_id: offer for offer in offers}
        bus.subscribe(PetTakenOffOffer, lambda event: self._set_on_offer(event.pet_id, False))
        bus.subscribe(PetBackOnOffer, lambda event: self._set_on_offer(event.pet_id, True))

    def find_available_pets(self, species: str | None = None, tag: str | None = None) -> list[PetOffer]:
        return [
            offer
            for offer in sorted(self._offers.values(), key=lambda offer: offer.pet_id)
            if offer.on_offer and _matches(offer, species, tag)
        ]

    def _set_on_offer(self, pet_id: int, on_offer: bool) -> None:
        self._offers[pet_id].on_offer = on_offer


def _matches(offer: PetOffer, species: str | None, tag: str | None) -> bool:
    species_ok = species is None or offer.species.lower() == species.lower()
    tag_ok = tag is None or tag.lower() in (t.lower() for t in offer.tags)
    return species_ok and tag_ok


class AvailablePet(BaseModel):
    pet_id: int
    name: str
    species: str
    tags: list[str]


def create_server(discovery: PetDiscovery, auth: AuthProvider | None = None) -> FastMCP:
    server = FastMCP("petstore-discovery", instructions=INSTRUCTIONS, auth=auth)

    @server.tool(title="Find available pets", annotations=ToolAnnotations(read_only_hint=True, idempotent_hint=True))
    def find_available_pets(
        species: Annotated[str | None, Field(description="e.g. dog, cat")] = None,
        tag: Annotated[str | None, Field(description="e.g. friendly, puppy, indoor")] = None,
    ) -> list[AvailablePet]:
        """Find pets on offer, optionally by species and tag."""
        return [
            AvailablePet(pet_id=o.pet_id, name=o.name, species=o.species, tags=list(o.tags))
            for o in discovery.find_available_pets(species, tag)
        ]

    return server
