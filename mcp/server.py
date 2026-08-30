#!/usr/bin/env python3
"""An MCP server over the YouTube surface geometry Engaged Views measured.

Speaks MCP over stdio as line-delimited JSON-RPC 2.0, with no third-party
dependencies at all. That is deliberate: this is meant to be runnable by anyone
with a Python 3 interpreter and nothing else, and a dependency is one more thing
that can be unavailable at the moment someone tries it.

WHAT THIS DOES NOT DO, and the omission is the point. It will not tell you where
a given title truncates. Predicting that needs font metrics for Roboto at a
specific size, which we have not measured -- so computing it here would be us
inventing the one number the tool exists to be trusted about. It hands you the
measured column width and the clamp rule and lets you measure text yourself.

Every response carries `measured_on` and the staleness caveat, because a
dimension is only true as of the day it was read off the page.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = json.load(open(os.path.join(HERE, "surfaces.json"), encoding="utf-8"))

# Revisions we know how to speak. We echo back whatever the client asked for if
# we recognise it, so a newer client does not get told a version it did not
# request; otherwise we answer with our newest.
KNOWN = ("2024-11-05", "2025-03-26", "2025-06-18")
DEFAULT_PROTOCOL = KNOWN[-1]

PROVENANCE = {
    "dataset": DATA["name"],
    "version": DATA["version"],
    "measured_on": DATA["measured_on"],
    "publisher": DATA["publisher"],
    "license": DATA["license"],
    "canonical_url": DATA["canonical_url"],
    "documentation": DATA["documentation"],
    "method": DATA["method"],
    "caveats": DATA["caveats"],
    "corrections": DATA["corrections"],
}

TOOLS = [
    {
        "name": "list_surfaces",
        "description": (
            "List every YouTube surface we have geometry for, with how each one was "
            "established (measured in a real browser, or sourced from a YouTube "
            "stylesheet) and which viewport widths exist for it."
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_surface_geometry",
        "description": (
            "Thumbnail box, title column width and title clamp rule for one surface. "
            "Returns only viewport widths that were actually measured -- it will not "
            "interpolate between them or extrapolate past them."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "surface_id": {
                    "type": "string",
                    "description": "One of: " + ", ".join(s["id"] for s in DATA["surfaces"]),
                },
                "viewport": {
                    "type": "string",
                    "description": "Viewport width in px. Omit for all measured widths.",
                },
            },
            "required": ["surface_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_dataset_provenance",
        "description": (
            "How these numbers were obtained: method, conditions, licence, known "
            "caveats, and the corrections we have published against our own earlier "
            "figures. Read this before relying on any dimension."
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]

STALE = (
    "These figures are true as of {d}. YouTube ships layout changes without notice and "
    "we do not re-measure on a schedule; re-check {u} before relying on them."
).format(d=DATA["measured_on"], u=DATA["canonical_url"])


def surface(sid):
    for s in DATA["surfaces"]:
        if s["id"] == sid:
            return s
    return None


def call_tool(name, args):
    if name == "list_surfaces":
        return {
            "surfaces": [
                {
                    "id": s["id"],
                    "label": s["label"],
                    "measurement": s["measurement"],
                    "viewports": sorted(s["viewports"], key=int),
                    "note": s.get("note"),
                }
                for s in DATA["surfaces"]
            ],
            "measured_on": DATA["measured_on"],
            "caveat": STALE,
        }

    if name == "get_surface_geometry":
        sid = (args or {}).get("surface_id")
        s = surface(sid)
        if s is None:
            valid = ", ".join(x["id"] for x in DATA["surfaces"])
            raise ValueError(f"unknown surface_id {sid!r}. Known surfaces: {valid}")
        vp = (args or {}).get("viewport")
        viewports = s["viewports"]
        if vp is not None:
            vp = str(vp)
            if vp not in viewports:
                have = ", ".join(sorted(viewports, key=int))
                raise ValueError(
                    f"viewport {vp} was not measured for {sid}. Measured widths: {have}. "
                    "We do not interpolate or extrapolate."
                )
            viewports = {vp: viewports[vp]}
        return {
            "id": s["id"],
            "label": s["label"],
            "measurement": s["measurement"],
            "viewports": viewports,
            "title_rule": s["title_rule"],
            "inset_px": s.get("inset_px"),
            "note": s.get("note"),
            "units": DATA["units"],
            "measured_on": DATA["measured_on"],
            "caveat": STALE,
        }

    if name == "get_dataset_provenance":
        return PROVENANCE

    raise ValueError(f"unknown tool {name!r}")


def handle(req):
    method = req.get("method")
    rid = req.get("id")

    if method == "initialize":
        asked = (req.get("params") or {}).get("protocolVersion")
        return {
            "protocolVersion": asked if asked in KNOWN else DEFAULT_PROTOCOL,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "engagedviews-surfaces", "version": DATA["version"]},
        }

    if method == "tools/list":
        return {"tools": TOOLS}

    if method == "tools/call":
        params = req.get("params") or {}
        try:
            result = call_tool(params.get("name"), params.get("arguments"))
        except ValueError as e:
            # A tool-level failure is a RESULT with isError, not a protocol
            # error -- the model is supposed to see it and correct itself.
            return {"content": [{"type": "text", "text": str(e)}], "isError": True}
        return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}

    raise LookupError(method)


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        # Notifications have no id and MUST NOT be answered.
        if "id" not in req:
            continue
        try:
            body = {"jsonrpc": "2.0", "id": req["id"], "result": handle(req)}
        except LookupError as e:
            body = {"jsonrpc": "2.0", "id": req["id"],
                    "error": {"code": -32601, "message": f"method not found: {e}"}}
        except Exception as e:  # never die on one bad request
            body = {"jsonrpc": "2.0", "id": req["id"],
                    "error": {"code": -32603, "message": f"internal error: {e}"}}
        sys.stdout.write(json.dumps(body) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
