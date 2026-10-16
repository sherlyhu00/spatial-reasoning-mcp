# spatial-reasoning-mcp

An MCP server that gives an LLM agent tool-level access to real geospatial
computation, so that spatial claims in an answer are computed against a named
source instead of recalled from model parameters.

## Why

Asked how far apart two places are, or how long a multi-stop trip takes, a
language model will usually produce a fluent number. The number is often wrong,
and nothing in the answer says where it came from. This server replaces that
guess with a tool call whose result carries the source and the parameters used.

Two design rules follow from that:

1. **Every result carries provenance.** Each tool returns `result`, `source`
   and `params`, so a caller can see which dataset and which settings produced
   the value.
2. **No silent fallback.** If a backend is unavailable or a place cannot be
   resolved, the tool raises an error. It never returns an estimate, because an
   estimate that looks like a measurement is the failure this server exists to
   prevent.

## What the difference looks like

Georgia Tech to Piedmont Park, Atlanta, as the tools report it:

| | value | source |
|---|---|---|
| `distance_between` | 2,874.9 m | great-circle distance on a sphere |
| `route_between`, drive | 5,022.0 m, 12.7 min | OSM routing via Valhalla (auto) |

The driving route is 1.75 times the straight line. A model answering from
memory produces one number somewhere in that range, with nothing in the answer
to say which quantity it meant or where it came from. Both numbers above state
what they are and what computed them.

## Tools

| Tool | What it does | Source |
|---|---|---|
| `geocode_place` | place name to coordinates | OSM / Nominatim |
| `reverse_geocode` | coordinates to the nearest addressable place | OSM / Nominatim |
| `distance_between` | great-circle distance between two points | WGS84 geodesic |
| `point_in_region` | which polygon of a GeoJSON layer contains a point | the GeoJSON file given |
| `route_between` | network distance and travel time between two points | OSM routing (see backends) |
| `order_stops` | visiting order minimising total travel time | OSM routing (see backends) |

`order_stops` searches orderings exhaustively and refuses more than eight stops,
so the returned order is optimal for the given travel-time matrix rather than a
heuristic the caller would have to trust.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

`osmnx` is only needed for the second routing backend below; without it the
other four tools and the default backend work.

## Routing backends

Set `SRM_ROUTING_BACKEND`:

**`valhalla`** (default) calls a hosted OpenStreetMap router, by default the
public FOSSGIS instance. Answers arrive in well under a second and nothing is
downloaded. It depends on a service being up, and the public instance is rate
limited; point `VALHALLA_URL` at your own instance for anything heavy.

**`osmnx`** downloads the street network for the area and routes locally. The
first call for an area is slow, because a walking network includes every
footpath and the cost grows with the square of the radius: tens of seconds for
a neighbourhood, minutes if `buffer_m` is widened. The graph is then cached in
`.cache/graphs` (override with `SRM_CACHE`) and later calls over the same area
take about a second.

The choice is a real trade-off, not a fallback. Use the hosted router when
latency matters; use the local graph when a number has to be reproducible
later from data you hold, or when there is no network.

## Limitations

The osmnx backend downloads a disc around the midpoint of the requested
points, so its cost grows with the square of the distance between them. It
suits a neighbourhood, not a city. Production routing engines avoid this by
preprocessing a whole region into a routing index; this project calls one
(Valhalla) rather than reimplementing it.

`order_stops` searches orderings exhaustively, which is why it stops at eight
stops. Beyond that the problem is the travelling salesman problem and wants a
heuristic, at which point "optimal" would no longer be the right word for what
is returned.

## Run

```bash
python -m spatial_reasoning_mcp
```

Register it with an MCP client (Claude Desktop, Claude Code, Cursor) by adding:

```json
{
  "mcpServers": {
    "spatial-reasoning": {
      "command": "python",
      "args": ["-m", "spatial_reasoning_mcp"],
      "cwd": "/absolute/path/to/spatial-reasoning-mcp"
    }
  }
}
```

## Tests

```bash
pip install pytest
python -m pytest tests -q
```

15 tests, none of which touch the network. The geocoding and routing tools are
covered for the behaviour that matters most -- that they raise instead of
returning a value they cannot compute -- and `order_stops` is tested against a
known distance function, so its optimality claim is checked rather than assumed.

## Notes

Nominatim's usage policy requires a identifying User-Agent and at most one
request per second; both are enforced in `geocode.py`. For heavy use, run your
own Nominatim instance and set `NOMINATIM_URL`.
