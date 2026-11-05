"""Identity Management: who the customer is. No tools: the customer logs into the app.

With OAuth (default) the customer comes from the Keycloak token. With AUTH=off (the
`tools` and `demo` modes, the wire trace, kagent, the emergency switch on stage) it
comes from PETSTORE_CUSTOMER instead. Tools never take the customer as a parameter.
"""

import os

from fastmcp.dependencies import Depends
from fastmcp.server.auth import RemoteAuthProvider
from fastmcp.server.auth.providers.jwt import JWTVerifier
from fastmcp.server.dependencies import get_access_token
from pydantic import AnyHttpUrl

CUSTOMER_CLAIM = "preferred_username"


class NotSignedIn(RuntimeError):
    """A tool was called without a customer: no token and AUTH is not off."""


def auth_enabled() -> bool:
    return os.environ.get("AUTH", "on") != "off"


def issuer() -> str:
    return os.environ.get("KEYCLOAK_ISSUER", "http://localhost:8080/realms/petstore")


def public_url() -> str:
    """The base URL the host sees; the token audience is <public_url>/<context>/mcp."""
    return os.environ.get("PUBLIC_URL", "http://localhost:8000")


def auth_provider(context: str) -> RemoteAuthProvider | None:
    """One protected resource per context: a sales token is no good on Pet Discovery."""
    if not auth_enabled():
        return None
    verifier = JWTVerifier(
        jwks_uri=f"{issuer()}/protocol/openid-connect/certs",
        issuer=issuer(),
        audience=f"{public_url()}/{context}/mcp",
        required_scopes=[f"petstore:{context}"],
    )
    return RemoteAuthProvider(
        token_verifier=verifier,
        authorization_servers=[AnyHttpUrl(issuer())],
        base_url=f"{public_url()}/{context}",
        resource_name=f"petstore-{context}",
    )


def current_customer() -> str:
    if not auth_enabled():
        return os.environ.get("PETSTORE_CUSTOMER", "alice")
    token = get_access_token()
    customer = token.claims.get(CUSTOMER_CLAIM) if token else None
    if not customer:
        raise NotSignedIn("No signed-in customer: the request carries no token with preferred_username.")
    return customer


def Customer() -> str:  # noqa: N802 (reads like TokenClaim at the call site)
    """Tool parameter default that injects the customer; it never shows up in the input schema."""
    return Depends(current_customer)
