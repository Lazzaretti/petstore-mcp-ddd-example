import json, httpx
K="http://localhost:8080"
tok=httpx.post(f"{K}/realms/master/protocol/openid-connect/token",data=dict(client_id="admin-cli",username="admin",password="admin",grant_type="password")).json()["access_token"]
h={"Authorization":f"Bearer {tok}"}
full=json.load(open("petstore-realm.json"))
scopes=full.pop("clientScopes"); optional=full.pop("defaultOptionalClientScopes")
clients=full.pop("clients"); profiles=full.pop("clientProfiles"); policies=full.pop("clientPolicies")
r=httpx.post(f"{K}/admin/realms",json=full,headers=h); print("realm",r.status_code,r.text[:200])
A=f"{K}/admin/realms/petstore"
for s in scopes:
    r=httpx.post(f"{A}/client-scopes",json=s,headers=h); print("scope",s["name"],r.status_code,r.text[:200])
allsc={s["name"]:s["id"] for s in httpx.get(f"{A}/client-scopes",headers=h).json()}
print(sorted(allsc))
for n in [f"petstore:{c}" for c in ("discovery","sales","handover")]:
    r=httpx.put(f"{A}/default-optional-client-scopes/{allsc[n]}",headers=h); print("optional",n,r.status_code)
for c in clients:
    r=httpx.post(f"{A}/clients",json=c,headers=h); print("client",c["clientId"],r.status_code,r.text[:200])
r=httpx.put(f"{A}/client-policies/profiles",json=profiles,headers=h); print("profiles",r.status_code,r.text[:300])
r=httpx.put(f"{A}/client-policies/policies",json=policies,headers=h); print("policies",r.status_code,r.text[:300])
