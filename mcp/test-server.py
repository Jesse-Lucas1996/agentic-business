#!/usr/bin/env python3
"""Drive server.py over real stdio JSON-RPC and check what comes back.

Exists because "it parses" is not "it works", and because the dataset it serves
is copied from site/api/ -- if those two ever drift, this server publishes
numbers the tool no longer renders, under our name, to agents that cannot check.
"""
import json
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parent
fails = []


def rpc(requests):
    payload = "".join(json.dumps(r) + "\n" for r in requests)
    out = subprocess.run([sys.executable, str(HERE / "server.py")], input=payload,
                         capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        fails.append(f"server exited {out.returncode}: {out.stderr[:400]}")
        return []
    return [json.loads(l) for l in out.stdout.splitlines() if l.strip()]


def check(cond, msg):
    if not cond:
        fails.append(msg)


# The published dataset is the source of truth; this copy must be identical.
a = json.loads((REPO / "site" / "api" / "surfaces.json").read_text())
b = json.loads((HERE / "surfaces.json").read_text())
check(a == b, "mcp/surfaces.json has DRIFTED from site/api/surfaces.json — "
              "the server would publish numbers the tool no longer renders")

r = rpc([
    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
     "params": {"protocolVersion": "2025-06-18", "capabilities": {}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},   # no id: must be ignored
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
     "params": {"name": "get_surface_geometry",
                "arguments": {"surface_id": "desktop-search", "viewport": "1280"}}},
    {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
     "params": {"name": "get_surface_geometry", "arguments": {"surface_id": "nonsense"}}},
    {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
     "params": {"name": "get_surface_geometry",
                "arguments": {"surface_id": "desktop-home", "viewport": "1440"}}},
    {"jsonrpc": "2.0", "id": 6, "method": "tools/call",
     "params": {"name": "get_dataset_provenance", "arguments": {}}},
    {"jsonrpc": "2.0", "id": 7, "method": "no/such/method"},
])

check(len(r) == 7, f"expected 7 responses for 8 messages (the notification must NOT be "
                   f"answered), got {len(r)}")
by_id = {x.get("id"): x for x in r}

check(by_id[1]["result"]["protocolVersion"] == "2025-06-18", "did not echo the client's protocol version")
check(by_id[1]["result"]["serverInfo"]["name"] == "engagedviews-surfaces", "wrong serverInfo")

names = {t["name"] for t in by_id[2]["result"]["tools"]}
check(names == {"list_surfaces", "get_surface_geometry", "get_dataset_provenance"},
      f"unexpected tool set: {names}")

geo = json.loads(by_id[3]["result"]["content"][0]["text"])
want = a["surfaces"]
want = next(s for s in want if s["id"] == "desktop-search")["viewports"]["1280"]
check(geo["viewports"]["1280"] == want, "geometry returned does not match the dataset")
check(geo["measured_on"] == a["measured_on"], "response omitted or altered measured_on")
check("true as of" in geo["caveat"], "response dropped the staleness caveat")

check(by_id[4]["result"].get("isError") is True, "an unknown surface must return isError, not crash")
check(by_id[5]["result"].get("isError") is True, "an UNMEASURED viewport must be refused, not interpolated")
check("do not interpolate" in by_id[5]["result"]["content"][0]["text"].lower(),
      "the refusal must say why")

prov = json.loads(by_id[6]["result"]["content"][0]["text"])
check(prov["license"] == a["license"] and prov["corrections"] == a["corrections"],
      "provenance does not match the dataset")

check("error" in by_id[7] and by_id[7]["error"]["code"] == -32601,
      "unknown method must be a -32601 JSON-RPC error")

if fails:
    print("FAIL")
    for f in fails:
        print("  !! " + f)
    sys.exit(1)
print(f"PASS — {len(r)} responses, protocol negotiated, notification ignored, "
      "unmeasured viewport refused, provenance and dataset identical.")
