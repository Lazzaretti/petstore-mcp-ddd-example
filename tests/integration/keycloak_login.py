"""TEST ONLY: a scripted browser login against the demo realm (authorization code + PKCE).

It fills in Keycloak's login form instead of a person, so the tests can get real tokens.
Never use this outside the tests: real clients open the browser.
"""

import base64
import hashlib
import secrets
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

import httpx2

from tests.integration.conftest import KEYCLOAK_ISSUER

CLIENT_ID = "petstore-demo-cli"
REDIRECT_URI = "http://localhost:33418/callback"


class _LoginForm(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.action: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "form" and self.action is None:
            self.action = dict(attrs).get("action")


def access_token(user: str, context: str) -> str:
    """Logs `user` in (local demo password) and returns a token for one server."""
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    resource = f"http://localhost:8000/{context}/mcp"
    with httpx2.Client(follow_redirects=False, timeout=20) as http:
        page = http.get(
            f"{KEYCLOAK_ISSUER}/protocol/openid-connect/auth",
            params={
                "response_type": "code",
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "scope": f"petstore:{context}",
                "resource": resource,
                "state": secrets.token_urlsafe(8),
                "code_challenge": challenge,
                "code_challenge_method": "S256",
            },
        )
        page.raise_for_status()
        form = _LoginForm()
        form.feed(page.text)
        assert form.action, "Keycloak login form not found"
        # Keycloak marks its cookies Secure; on plain-http localhost they must be sent by hand.
        cookies = "; ".join(f"{c.name}={c.value}" for c in page.cookies.jar)
        login = http.post(form.action, data={"username": user, "password": f"{user}-demo"}, headers={"Cookie": cookies})
        code = parse_qs(urlparse(login.headers["location"]).query)["code"][0]
        token = http.post(
            f"{KEYCLOAK_ISSUER}/protocol/openid-connect/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
                "client_id": CLIENT_ID,
                "code_verifier": verifier,
                "resource": resource,
            },
        )
        token.raise_for_status()
        return token.json()["access_token"]
