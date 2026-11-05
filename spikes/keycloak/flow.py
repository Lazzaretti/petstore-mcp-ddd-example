import base64, hashlib, json, os, sys, secrets, urllib.parse as up
import httpx, jwt
from bs4 import BeautifulSoup
ISS = "http://localhost:8080/realms/petstore"
def run(client_id, redirect_uri, scope, resource=None, token_resource="same", user="alice", show=True):
    v = secrets.token_urlsafe(48)
    ch = base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()
    p = dict(response_type="code", client_id=client_id, redirect_uri=redirect_uri, scope=scope,
             state="xyz", code_challenge=ch, code_challenge_method="S256")
    if resource: p["resource"] = resource
    with httpx.Client(follow_redirects=False, timeout=20) as c:
        r = c.get(f"{ISS}/protocol/openid-connect/auth", params=p)
        if r.status_code in (302, 303) and "error=" in r.headers.get("location", ""):
            return {"auth_error_redirect": r.headers["location"]}
        if r.status_code != 200:
            return {"auth_status": r.status_code, "body": r.text[:300]}
        form = BeautifulSoup(r.text, "html.parser").find("form")
        if form is None:
            return {"auth_page_no_form": BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)[:300]}
        ck = "; ".join(f"{k}={v}" for k, v in r.cookies.items())
        r = c.post(form["action"], data={"username": user, "password": f"{user}-demo", "credentialId": ""}, headers={"Cookie": ck})
        loc = r.headers.get("location")
        if not loc:
            txt = BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)[:400]
            # consent screen?
            f2 = BeautifulSoup(r.text, "html.parser").find("form")
            if f2 is not None and "accept" in r.text:
                r = c.post(f2["action"], headers={"Cookie": ck}, data={"accept": "Yes", "code": f2.find("input", {"name": "code"})["value"] if f2.find("input", {"name": "code"}) else ""})
                loc = r.headers.get("location")
            if not loc:
                return {"login_status": r.status_code, "text": txt}
        ck = "; ".join(f"{k}={v}" for k, v in {**dict(r.cookies.items()), **dict(c.cookies.items())}.items())
        if "login-actions/required-action" in loc:
            g = c.get(loc, headers={"Cookie": ck})
            soup = BeautifulSoup(g.text, "html.parser"); f3 = soup.find("form")
            consent_text = soup.get_text(" ", strip=True)[:500]
            data = {i["name"]: i.get("value", "") for i in f3.find_all("input") if i.get("name")}
            data["accept"] = "Yes"
            r = c.post(up.urljoin("http://localhost:8080/", f3["action"]), data=data, headers={"Cookie": ck})
            loc = r.headers.get("location")
            print("CONSENT PAGE:", consent_text, file=sys.stderr)
        q = dict(up.parse_qsl(up.urlparse(loc).query))
        if "code" not in q:
            return {"redirect": loc}
        td = dict(grant_type="authorization_code", code=q["code"], redirect_uri=redirect_uri, client_id=client_id, code_verifier=v)
        tr = resource if token_resource == "same" else token_resource
        if tr: td["resource"] = tr
        t = c.post(f"{ISS}/protocol/openid-connect/token", data=td)
        out = {"iss_in_auth_response": q.get("iss"), "token_status": t.status_code}
        tj = t.json()
        if "access_token" in tj:
            cl = jwt.decode(tj["access_token"], options={"verify_signature": False})
            out["_at"] = tj["access_token"]; out.update({k: cl.get(k) for k in ("aud", "azp", "scope", "preferred_username", "sub")})
            out["has_refresh"] = "refresh_token" in tj
            out["refresh_typ"] = jwt.decode(tj["refresh_token"], options={"verify_signature": False}).get("typ") if "refresh_token" in tj else None
        else:
            out["token_error"] = tj
        return out
if __name__ == "__main__":
    print(json.dumps(run(*json.loads(sys.argv[1])), indent=1))
