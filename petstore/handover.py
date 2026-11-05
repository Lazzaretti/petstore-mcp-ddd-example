"""Pet Handover -> petstore-handover: the customer's purchases and their pickup slots.

A read model fed by Pet Sales' events. Picking the pet up happens in the shop: no tool.
"""

from dataclasses import dataclass

from fastmcp import FastMCP
from fastmcp.server.auth import AuthProvider
from mcp_types import ToolAnnotations
from pydantic import BaseModel

from petstore.events import EventBus, PetPurchased, PickupScheduled, PurchaseCancelled, Slot
from petstore.identity import Customer

INSTRUCTIONS = "Pet Handover: the signed-in customer's purchases and when to pick them up."
INSTRUCTIONS_WITHOUT_PICKUP = "Pet Handover: the signed-in customer's purchases."


@dataclass
class PurchaseView:
    purchase_id: str
    customer: str
    pet: str
    pickup: Slot | None


class PetHandover:
    def __init__(self, bus: EventBus) -> None:
        self._purchases: dict[str, PurchaseView] = {}
        bus.subscribe(PetPurchased, self._purchased)
        bus.subscribe(PickupScheduled, self._pickup_scheduled)
        bus.subscribe(PurchaseCancelled, self._cancelled)

    def purchases_of(self, customer: str) -> list[PurchaseView]:
        """Active purchases only, in the order they were made."""
        return [view for view in self._purchases.values() if view.customer == customer]

    def _purchased(self, event: PetPurchased) -> None:
        self._purchases[event.purchase_id] = PurchaseView(
            event.purchase_id, event.customer, event.pet_name, event.pickup_slot
        )

    def _pickup_scheduled(self, event: PickupScheduled) -> None:
        self._purchases[event.purchase_id].pickup = event.pickup_slot

    def _cancelled(self, event: PurchaseCancelled) -> None:
        self._purchases.pop(event.purchase_id, None)


class MyPurchase(BaseModel):
    purchase_id: str
    pet: str


class MyPurchaseWithPickup(MyPurchase):
    pickup: Slot | None


def create_server(handover: PetHandover, auth: AuthProvider | None = None, pickup: bool = True) -> FastMCP:
    """With PICKUP=off, my_purchases leaves out the pickup slot."""
    server = FastMCP(
        "petstore-handover", instructions=INSTRUCTIONS if pickup else INSTRUCTIONS_WITHOUT_PICKUP, auth=auth
    )
    read_only = ToolAnnotations(read_only_hint=True, idempotent_hint=True)

    if pickup:

        @server.tool(title="My purchases", annotations=read_only)
        def my_purchases(customer: str = Customer()) -> list[MyPurchaseWithPickup]:
            """The customer's active purchases with their pickup slots."""
            views = handover.purchases_of(customer)
            return [MyPurchaseWithPickup(purchase_id=v.purchase_id, pet=v.pet, pickup=v.pickup) for v in views]

    else:

        @server.tool(title="My purchases", annotations=read_only)
        def my_purchases(customer: str = Customer()) -> list[MyPurchase]:
            """The customer's active purchases."""
            return [MyPurchase(purchase_id=v.purchase_id, pet=v.pet) for v in handover.purchases_of(customer)]

    return server
