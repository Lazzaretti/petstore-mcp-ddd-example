import asyncio, sys, urllib.parse as up
import httpx
from bs4 import BeautifulSoup
from fastmcp import Client
from fastmcp.client.auth import OAuth
from key_value.aio.stores.disk import DiskStore

LOG = []
class ScriptedLoginOAuth(OAuth):
    """TEST ONLY: replaces the browser by scraping the Keycloak login form."""
    async def redirect_handler(self, authorization_url: str) -> None:
        LOG.append(dict(up.parse_qsl(up.urlparse(authorization_url).query)))
        asyncio.get_running_loop().create_task(self._login(authorization_url))
    async def _login(self, url):
        async with httpx.AsyncClient(follow_redirects=False) as c:
            r = await c.get(url); ck = "; ".join(f"{k}={v}" for k, v in r.cookies.items())
            f = BeautifulSoup(r.text, "html.parser").find("form")
            r = await c.post(f["action"], data={"username": "alice", "password": "alice-demo"}, headers={"Cookie": ck})
            loc = r.headers["location"]
            for _ in range(50):
                try:
                    await c.get(loc); return
                except httpx.ConnectError:
                    await asyncio.sleep(0.1)

async def main():
    store = DiskStore(directory=sys.argv[1])
    oauth = ScriptedLoginOAuth(client_id="petstore-demo-cli", callback_port=33418, token_storage=store)
    async with Client("http://localhost:8000/sales/mcp", auth=oauth) as c:
        print((await c.call_tool("reserve_pet", {"pet_id": "dog-3"})).data)
    print("authorization request params:", {k: v for k, v in (LOG[0].items() if LOG else []) if k != "code_challenge"})
asyncio.run(main())
