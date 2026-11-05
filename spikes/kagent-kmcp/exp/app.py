"""Experiment: three FastMCP 4.1.4 servers mounted in one Starlette app."""
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount

from fastmcp import Context, FastMCP
from fastmcp.server.elicitation import parse_elicit_response_type
from fastmcp.utilities.lifespan import combine_lifespans
from mcp.types import ElicitRequest, ElicitRequestFormParams, InputRequiredResult, ToolAnnotations

SLOTS = ["Sat 10:00", "Sat 14:00", "Mon 17:00"]

discovery = FastMCP("petstore-discovery")
sales = FastMCP("petstore-sales")
handover = FastMCP("petstore-handover")


@discovery.tool(annotations=ToolAnnotations(readOnlyHint=True))
def find_available_pets(species: str | None = None) -> list[dict]:
    """Find pets that are available for adoption/purchase."""
    return [{"id": "rex", "species": "dog"}]


@sales.tool
def reserve_pet(pet_id: str) -> str:
    """Reserve a pet for a customer."""
    return f"reserved {pet_id}"


@sales.tool
async def buy_pet(pet_id: str, ctx: Context) -> str | InputRequiredResult:
    """Buy a reserved pet; asks the customer for a pickup slot."""
    version = ctx.request_context.protocol_version
    if version == "2026-07-28":
        responses = ctx.input_responses
        if responses is None:
            schema = parse_elicit_response_type(SLOTS, response_title="Pickup slot").schema
            return InputRequiredResult(
                result_type="input_required",
                input_requests={
                    "slot": ElicitRequest(
                        method="elicitation/create",
                        params=ElicitRequestFormParams(
                            message=f"When do you want to pick up {pet_id}?",
                            requested_schema=schema,
                        ),
                    )
                },
                request_state=f"pet={pet_id}",
            )
        answer = responses["slot"]
        if answer.action != "accept":
            return f"purchase of {pet_id} not completed ({answer.action})"
        return f"[modern] bought {pet_id}, pickup {answer.content['value']} (state={ctx.request_state})"
    # handshake era
    result = await ctx.elicit(f"When do you want to pick up {pet_id}?", response_type=SLOTS, response_title="Pickup slot")
    if result.action != "accept":
        return f"purchase of {pet_id} not completed ({result.action})"
    return f"[legacy {version}] bought {pet_id}, pickup {result.data}"


@sales.tool(annotations=ToolAnnotations(destructiveHint=True))
def cancel_purchase(purchase_id: str) -> str:
    """Cancel a purchase."""
    return f"cancelled {purchase_id}"


@sales.resource("pet-sales://policies", mime_type="text/markdown")
def policies() -> str:
    """Sales policies."""
    return "# Policies\nReservations expire after 24h."


@sales.custom_route("/stock", methods=["GET"])
async def stock(request: Request) -> JSONResponse:
    return JSONResponse({"dogs": 3, "cats": 1})


@handover.tool(annotations=ToolAnnotations(readOnlyHint=True))
def my_purchases() -> list[str]:
    """List my purchases."""
    return []


d_app = discovery.http_app(path="/mcp")
s_app = sales.http_app(path="/mcp")
h_app = handover.http_app(path="/mcp")

app = Starlette(
    routes=[
        Mount("/discovery", app=d_app),
        Mount("/sales", app=s_app),
        Mount("/handover", app=h_app),
    ],
    lifespan=combine_lifespans(d_app.lifespan, s_app.lifespan, h_app.lifespan),
)
