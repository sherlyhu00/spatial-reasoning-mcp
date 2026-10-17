# spatial-reasoning-mcp

An MCP server that gives an LLM agent real geospatial computation as tools, so
that spatial claims in an answer are computed from a named source rather than
recalled from the model's parameters.

## Why

Ask a language model how far apart two places are, or how long a multi-stop
trip takes, and it will produce a confident number. The number is often wrong,
and nothing in the answer says where it came from.

This server answers those questions with a tool call instead. Two rules follow:

1. **Every result carries its provenance.** Each tool returns `result`,
   `source` and `params`, so the caller can see what produced the value and
   with which settings.
2. **No silent fallback.** If a place cannot be resolved or a router is
   unavailable, the tool raises. It does not return an estimate, because an
   estimate that reads like a measurement is the problem this server addresses.

## An example

Georgia Tech to Piedmont Park, Atlanta:

| | value | source |
|---|---|---|
| `distance_between` | 2,874.9 m | spherical distance, R = 6,371,008.8 m |
| `route_between`, drive | 5,022.0 m, 12.7 min | OSM routing via Valhalla (auto) |

The driving route is 1.75 times the straight line. A model answering from
memory gives one number somewhere in that range, with no way to tell which
quantity it meant. Both numbers above say what they are and what computed them.

## Tools

| Tool | What it does | Source |
|---|---|---|
| `geocode_place` | place name to coordinates | OSM / Nominatim |
| `reverse_geocode` | coordinates to the nearest addressable place | OSM / Nominatim |
| `distance_between` | great-circle distance between two points | spherical Earth model |
| `point_in_region` | which polygon of a GeoJSON layer contains a point | the layer you pass in |
| `route_between` | network distance and travel time | OSM routing (see backends) |
| `order_stops` | visiting order with the shortest total travel time | OSM routing (see backends) |

`order_stops` searches orderings exhaustively and accepts at most eight stops,
so the order it returns is optimal for its travel-time matrix rather than a
heuristic the caller has to trust.

## Install and run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m spatial_reasoning_mcp
```

The server communicates over stdio, so on its own it will sit there waiting for
a client. Register it with one (Claude Desktop, Claude Code, Cursor):

```json
{
  "mcpServers": {
    "spatial-reasoning": {
      "command": "/absolute/path/to/.venv/bin/python",
      "args": ["-m", "spatial_reasoning_mcp"],
      "cwd": "/absolute/path/to/spatial-reasoning-mcp"
    }
  }
}
```

To see the tools work without a client, run `python scripts/smoke.py`, which
calls each one against live data and prints the results.

## Routing backends

Set `SRM_ROUTING_BACKEND` to choose. All six tools work on either.

**`valhalla`** (default) calls a hosted OpenStreetMap router, by default the
public FOSSGIS instance. It answers in under a second and downloads nothing.
It needs that service to be up, and the public instance is rate limited, so
point `VALHALLA_URL` at your own instance for heavy use.

**`osmnx`** downloads the street network for the area and routes locally. It
needs `osmnx` and `networkx` installed. The first call for an area is slow: a
walking network includes every footpath, and the cost grows with the square of
the radius, so expect tens of seconds for a neighborhood. The graph is cached
in `.cache/graphs` afterwards, and later calls over the same area take about a
second. Set `SRM_CACHE` to move that cache.

This is a trade-off, not a fallback. Use the hosted router when latency
matters, and the local graph when a number has to be reproducible later from
data you hold, or when there is no network.

## Tests

```bash
pip install pytest
python -m pytest tests -q
```

18 tests, none of which touch the network. The geocoding and routing tools are
covered for the behavior that matters most, that they raise instead of
returning a value they could not compute. `order_stops` is tested against a
known travel-time matrix, so its optimality claim is checked rather than
assumed.

## Evaluation

Three harnesses in `eval/`, covering accuracy, latency and scaling. Each states
what it measured against: distance is scored against geopy's geodesic rather
than against this server's own output, and routing is treated as having no
absolute ground truth, because a travel time is whatever a particular network
and speed model says it is. See `eval/README.md`.

```bash
python eval/make_benchmark.py   # resolve and freeze 12 place pairs
python eval/accuracy.py         # error against an independent geodesic
python eval/latency.py 5        # per-tool latency, local and network separated
python eval/scaling.py          # how cost grows with the number of stops
```

### Results

Measured 17 October 2026 on an M-series MacBook Air, routing backend
`valhalla` against the public FOSSGIS instance, client in Shanghai.

**Accuracy of `distance_between`**, 12 pairs from 1 km to 27 km, scored against
geopy's WGS84 geodesic:

| | median error | worst error |
|---|---|---|
| this server | 0.18 % | 0.31 % |
| [MODEL NAME], from memory, no tools | 1.7 % | 13.1 % |

The server's error is the cost of modeling the Earth as a sphere rather than an
ellipsoid. It is now a measured bound rather than an assumption: at 25 km the
worst case is about 75 m. The approximation is kept because it needs no
dependency and no network; anything needing survey accuracy should use a
geodesic.

Three things matter more than the ratio of medians.

The benchmark favors the model. All twelve pairs are world-famous landmarks
whose distances appear repeatedly in text. On ordinary streets or census-tract
centroids the gap would be wider, so 9x is a floor, not a typical figure.

The model's error is unpredictable rather than large. It was 0.2 % on the
Eiffel Tower pair and 13.1 % on the Georgia Tech pair, with nothing in either
answer to say which kind it was. The server's error has a known ceiling.

The model's absolute error barely tracks distance: about 110 m typically and up
to 550 m, whether the question spans 1 km or 27 km. Relative error is therefore
worst at short range, which is the range that first- and last-mile and
itinerary questions live in.

**Latency**, median of five calls:

| tool | median |
|---|---|
| `distance_between` | under 0.1 ms |
| `geocode_place` | 994 ms |
| `reverse_geocode` | 1,031 ms |
| `route_between` | 1,025 ms |

The two geocoding figures are dominated by the one-request-per-second limit the
client enforces for Nominatim, not by the service. The routing figure is a real
round trip to Germany; a nearer or self-hosted Valhalla would cut it.

**Scaling** of `order_stops`, against a stub router so the figure is this
project's own search:

| stops | orderings | search |
|---|---|---|
| 4 | 6 | 0.02 ms |
| 6 | 120 | 0.10 ms |
| 8 | 5,040 | 4.51 ms |

Each additional stop multiplies the search by n−1: nine stops would be 8x the
work of eight, twelve stops 7,920x. The eight-stop limit is where exhaustive
search stops being affordable, and therefore where the word "optimal" would
stop being honest.

**Not measured.** Whether an agent using these tools answers better than one
answering from memory. That needs an end-to-end agent benchmark with a task set
and a definition of correct, which this evaluation does not attempt. What is
measured above is the accuracy of the computation the tools perform, and the
cost of performing it.

## Limitations

The `osmnx` backend downloads a disc around the midpoint of the points it is
given, so its cost grows with the square of the distance between them. It suits
a neighborhood, not a city. Routing engines avoid this by preprocessing a whole
region into an index; this project calls one rather than reimplementing it.

`order_stops` stops at eight stops because the search is exhaustive. Beyond
that this is the traveling salesman problem and needs a heuristic, at which
point "optimal" would stop being the right word for what is returned.

Nominatim's usage policy requires an identifying User-Agent and at most one
request per second. Both are enforced in `geocode.py`; set `NOMINATIM_URL` and
`NOMINATIM_USER_AGENT` to use your own instance.
