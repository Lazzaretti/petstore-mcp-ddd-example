import json, sys
for l in open(sys.argv[1]):
    e = json.loads(l)
    if e["kind"] == "response.start":
        print(f"<-- HTTP {e['info']} {e['headers']}"); continue
    if e["kind"] == "request":
        h = {k: v for k, v in (e["headers"] or {}).items() if k.startswith("mcp")}
        print(f"--> {e['info']} {h}\n    {e['body']}")
    else:
        print(f"<-- {e['body'].strip()}")
