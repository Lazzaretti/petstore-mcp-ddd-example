"""The composition root: seeds the contexts, wires them to the bus and mounts the three servers.

Modes: serve (the servers), tools (what the agent sees, for the numbers slide), demo (the scripted run).
"""

import argparse
import asyncio
import os
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from datetime import datetime

import uvicorn
from fastmcp import FastMCP
from fastmcp.utilities.lifespan import combine_lifespans
from starlette.applications import Starlette
from starlette.routing import BaseRoute, Mount

from petstore import discovery, handover, identity, sales
from petstore.events import EventBus, create_bus
from petstore.sales import Clock, PetSales, PetStatus, random_id, reservation_hold_from_env

SWEEP_INTERVAL_SECONDS = 30


@dataclass(frozen=True)
class SeedPet:
    pet_id: int
    name: str
    species: str
    tags: tuple[str, ...]
    sold: bool = False


# Bello is a second friendly dog, so the agent has to ask which one; Max is sold from the start.
SEED_PETS = (
    SeedPet(1, "Rex", "dog", ("friendly",)),
    SeedPet(2, "Mia", "cat", ("indoor",)),
    SeedPet(3, "Bello", "dog", ("puppy", "friendly")),
    SeedPet(4, "Max", "dog", ("friendly",), sold=True),
)


def pickup_from_env() -> bool:
    """PICKUP=off: the original Petstore API's scope (no pickup), for a fair comparison."""
    setting = os.environ.get("PICKUP", "on")
    if setting not in ("on", "off"):
        raise ValueError(f"PICKUP={setting!r}: use on or off")
    return setting == "on"


@dataclass(frozen=True)
class Petstore:
    bus: EventBus
    clock: Clock
    pickup: bool
    discovery: discovery.PetDiscovery
    sales: PetSales
    handover: handover.PetHandover


def create_petstore(
    now: datetime | None = None, new_id: Callable[[str], str] = random_id, pickup: bool | None = None
) -> Petstore:
    """A fresh in-memory shop (reset = restart). `now` fixes the clock; otherwise PETSTORE_NOW or real time.
    `pickup` defaults to PICKUP."""
    pickup = pickup_from_env() if pickup is None else pickup
    bus = create_bus()
    clock = Clock(fixed=now) if now else Clock.from_env()
    offers = [discovery.PetOffer(p.pet_id, p.name, p.species, p.tags, on_offer=not p.sold) for p in SEED_PETS]
    pets = [
        sales.Pet(p.pet_id, p.name, p.species, p.tags, PetStatus.SOLD if p.sold else PetStatus.AVAILABLE)
        for p in SEED_PETS
    ]
    hold = reservation_hold_from_env()
    return Petstore(
        bus=bus,
        clock=clock,
        pickup=pickup,
        discovery=discovery.PetDiscovery(offers, bus),
        sales=PetSales(pets, bus=bus, clock=clock, reservation_hold=hold, new_id=new_id, pickup=pickup),
        handover=handover.PetHandover(bus),
    )


def create_servers(petstore: Petstore | None = None) -> dict[str, FastMCP]:
    petstore = petstore or create_petstore()
    return {
        "discovery": discovery.create_server(petstore.discovery, identity.auth_provider("discovery")),
        "sales": sales.create_server(petstore.sales, identity.auth_provider("sales")),
        "handover": handover.create_server(
            petstore.handover, identity.auth_provider("handover"), pickup=petstore.pickup
        ),
    }


def create_app(petstore: Petstore | None = None) -> Starlette:
    petstore = petstore or create_petstore()
    servers = create_servers(petstore)
    http_apps = {context: server.http_app(path="/mcp") for context, server in servers.items()}
    routes: list[BaseRoute] = [*_well_known_routes(servers)]
    routes += [Mount(f"/{context}", app=http_app) for context, http_app in http_apps.items()]
    lifespans = [http_app.lifespan for http_app in http_apps.values()]
    return Starlette(routes=routes, lifespan=combine_lifespans(*lifespans, reservation_sweeper(petstore.sales)))


def _well_known_routes(servers: dict[str, FastMCP]) -> list[BaseRoute]:
    """Protected resource metadata lives at the app root (RFC 9728), not under the mount."""
    providers = [server.auth for server in servers.values() if server.auth]
    return [route for provider in providers for route in provider.get_well_known_routes(mcp_path="/mcp")]


def reservation_sweeper(
    pet_sales: PetSales, every: float = SWEEP_INTERVAL_SECONDS
) -> Callable[[Starlette], AbstractAsyncContextManager[None]]:
    """Expires reservations without a call, so Pet Discovery gets PetBackOnOffer on time."""

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async def sweep() -> None:
            while True:
                await asyncio.sleep(every)
                pet_sales.expire_reservations()

        task = asyncio.create_task(sweep())
        try:
            yield
        finally:
            task.cancel()

    return lifespan


def serve() -> None:
    # 0.0.0.0: FastMCP's host guard answers 421 to non-localhost Host headers (kind) otherwise.
    uvicorn.run(create_app(), host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))


def tools() -> None:
    from petstore import numbers  # imports this module: load it only for this mode

    os.environ["AUTH"] = "off"
    print(asyncio.run(numbers.report()))


def demo(until: int, pause: bool) -> None:
    from petstore import demo as scripted  # imports this module: load it only for this mode

    asyncio.run(scripted.run(until=until, pause=pause))


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m petstore.app")
    parser.add_argument("mode", choices=["serve", "tools", "demo"])
    parser.add_argument("--until", type=int, default=8, help="demo: last scene (5 for the recording)")
    parser.add_argument("--pause", action="store_true", help="demo: wait for Enter after each scene")
    arguments = parser.parse_args()
    if arguments.mode == "demo":
        demo(arguments.until, arguments.pause)
    else:
        {"serve": serve, "tools": tools}[arguments.mode]()


if __name__ == "__main__":
    main()
