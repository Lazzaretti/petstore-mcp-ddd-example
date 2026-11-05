"""Three bounded-context MCP servers, one ASGI app, Keycloak as AS (research spike)."""
import contextlib
from fastmcp import FastMCP
from fastmcp.server.auth import RemoteAuthProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.dependencies import TokenClaim
from pydantic import AnyHttpUrl
from starlette.applications import Starlette
from starlette.routing import Mount

ISSUER = "http://localhost:8080/realms/petstore"
PUBLIC = "http://localhost:8000"

def keycloak_auth(context: str) -> RemoteAuthProvider:
    resource = f"{PUBLIC}/{context}/mcp"              # canonical URI = PRM "resource" = token "aud"
    verifier = JWTVerifier(
        jwks_uri=f"{ISSUER}/protocol/openid-connect/certs",
        issuer=ISSUER,
        audience=resource,                            # RFC 8707 / MCP: reject tokens for other servers
        required_scopes=[f"petstore:{context}"],
    )
    return RemoteAuthProvider(
        token_verifier=verifier,
        authorization_servers=[AnyHttpUrl(ISSUER)],
        base_url=f"{PUBLIC}/{context}",               # mount prefix goes here; mcp path "/mcp" is appended
        resource_name=f"Petstore {context}",
    )

auths = {c: keycloak_auth(c) for c in ("discovery", "sales", "handover")}
discovery = FastMCP("Petstore Discovery", auth=auths["discovery"])
sales = FastMCP("Petstore Sales", auth=auths["sales"])
handover = FastMCP("Petstore Handover", auth=auths["handover"])

@discovery.tool
def find_pets(species: str) -> list[str]:
    """Find available pets by species."""
    return [f"{species}-1", f"{species}-2"]

@sales.tool
def reserve_pet(pet_id: str, customer: str = TokenClaim("preferred_username")) -> str:
    """Reserve a pet for the signed-in customer."""
    return f"{pet_id} reserved for {customer}"

@sales.tool
def my_purchases(customer: str = TokenClaim("preferred_username")) -> list[str]:
    """List the signed-in customer's purchases."""
    return [f"purchase-of-{customer}"]

@handover.tool
def schedule_pickup(pet_id: str, customer: str = TokenClaim("preferred_username")) -> str:
    return f"pickup of {pet_id} for {customer}"

apps = {c: s.http_app(path="/mcp") for c, s in (("discovery", discovery), ("sales", sales), ("handover", handover))}

@contextlib.asynccontextmanager
async def lifespan(app):
    async with contextlib.AsyncExitStack() as stack:
        for a in apps.values():
            await stack.enter_async_context(a.lifespan(app))
        yield

well_known = [r for c, a in auths.items() for r in a.get_well_known_routes(mcp_path="/mcp")]
app = Starlette(routes=[*well_known, *(Mount(f"/{c}", app=a) for c, a in apps.items())], lifespan=lifespan)
