# engagedviews-surfaces

An MCP server over the YouTube surface geometry that Engaged Views measured.

It answers, for an agent building or checking a video listing: how wide is the thumbnail box
YouTube actually paints on this surface, how wide is the column the title has to fit into, and
how many lines does it clamp to. Four surfaces, three desktop viewport widths.

## What it will not do, on purpose

**It will not tell you where a title truncates.** Predicting that needs font metrics for Roboto
at a specific size, which we have not measured — so computing it here would mean inventing the
one number this is supposed to be trusted about. It gives you the measured column width and the
clamp rule and lets you measure the text yourself.

It will also refuse a viewport width we did not measure rather than interpolating to it, and it
says so in the refusal.

## Provenance, which is the whole point

Every dimension is either **measured** — read off YouTube's own rendered page in headless
Firefox with `getBoundingClientRect` — or **sourced** from a YouTube stylesheet we downloaded
and checked in, and each one is labelled with which. Every response carries `measured_on` and a
staleness caveat, because a dimension is only true as of the day it was read.

`get_dataset_provenance` returns the method, the conditions, the caveats, and **the corrections
we have published against our own earlier figures** — we shipped three wrong thumbnail boxes
once and the record of that ships with the data.

Canonical dataset: <https://engagedviews.com/api/surfaces.json> (CC BY 4.0)
Provenance page: <https://engagedviews.com/sources/>

## Run it

No dependencies beyond Python 3.

```bash
python3 server/server.py     # speaks MCP over stdio
python3 server/test-server.py  # drives it over real JSON-RPC and checks the answers
```

```json
{
  "mcpServers": {
    "engagedviews-surfaces": {
      "command": "python3",
      "args": ["/absolute/path/to/server/server.py"]
    }
  }
}
```

## Status

**Published to the MCP Registry as `com.engagedviews/surfaces` v1.0.2**, on 2026-08-30, in the
`com.engagedviews/*` namespace we hold by HTTP domain challenge. Verified by fetching the index
rather than by trusting the publisher's success message:

```
GET https://registry.modelcontextprotocol.io/v0/servers?search=com.engagedviews
  -> count 1, name com.engagedviews/surfaces, status active
```

The listing points at the `.mcpb` on this repo's v1.0.2 release; its `fileSha256` matches the
published asset, and the server inside it has been downloaded and run from a clean directory.
