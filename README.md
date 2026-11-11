# Spatial Reasoning MCP

Plan a day from a list of places and appointments. A local AI client calls this
Python MCP server to resolve places, estimate travel time, check arrival
constraints, and return an itinerary with map markers and calendar reminders.
The same server also handles one-off questions about routes, distances, and
geographic boundaries.

## Quick start

Use Python 3.10 or newer. From the repository root on macOS or Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install .
codex mcp add spatial-reasoning -- "$(pwd)/.venv/bin/python" -m spatial_reasoning_mcp
codex mcp list
```

Start a new Codex session to load the server. In another MCP client, configure a
local stdio server with the absolute path to `.venv/bin/python` as its command
and `-m spatial_reasoning_mcp` as its arguments. The client starts the process
and discovers the tools. The default providers require internet access.

## Plan a day

Try this in your MCP client:

> Plan a day in Atlanta. Start from Georgia Tech at 09:00 on December 3, 2026.
> Spend 45 minutes at Piedmont Park, then arrive at the High Museum of Art at
> 12:30 and spend 90 minutes there. Walk, allow 10 minutes of buffer per leg,
> and remind me 5 minutes before departure. Save the itinerary as an ICS file.

1. The client calls `geocode_place` for the origin and each stop. Add the city to
   the query, inspect the returned names, and resolve ambiguous matches.
2. The client calls `plan_day` with the resolved places in visiting order. Give
   the itinerary a stable ID, pass an IANA zone such as `America/New_York`,
   and include UTC offsets in timestamps. Each stop needs `stay_minutes`.
   Set a stop's `starts_at` for a fixed appointment. Omit it to start as early
   as feasible.
3. The server calculates travel time with the configured router and adds the
   requested buffer. If a fixed appointment cannot be reached, it reports
   the earliest feasible arrival. The client can then ask which constraint
   can move.
4. Present the returned `items` as a chronological list. Save the `ics` string
   as an `.ics` file and import it into a calendar with notifications enabled.
   Each travel event carries a departure alarm. The calendar app delivers it,
   including after the MCP client exits. Import and alarm behavior varies by
   calendar app. Use `geojson` to plot numbered stop markers in Leaflet.

The planner follows the supplied order within one local day and uses one
transport mode. Calendar import is a separate step. The server has no calendar
account integration, background scheduler, live traffic refresh, or map UI.
The GeoJSON includes points for stops. Route geometry is currently unavailable.

## Tools and project structure

- [server.py](spatial_reasoning_mcp/server.py) registers the tools with the Python
  MCP SDK. [__main__.py](spatial_reasoning_mcp/__main__.py) starts the stdio server.
- [geocode.py](spatial_reasoning_mcp/geocode.py) implements `geocode_place`
  and `reverse_geocode` using OpenStreetMap Nominatim.
- [geometry.py](spatial_reasoning_mcp/geometry.py) implements
  `distance_between` for great-circle distance and `point_in_region`
  for lookup against a local GeoJSON boundary layer.
- [routing.py](spatial_reasoning_mcp/routing.py) implements `route_between`
  and `order_stops` for walk, bike, and drive. `order_stops` keeps the first
  point fixed and minimizes travel time for up to eight points. It does not
  account for appointment windows. Use `plan_day` to validate the resulting
  order against those windows.
- [itinerary.py](spatial_reasoning_mcp/itinerary.py) schedules activities and
  travel legs, then exports the same schedule as items, GeoJSON, and iCalendar.

The host chooses and invokes tools. The service modules do the calculations and
return data from named sources. To add a tool, implement and test its behavior
in a service module, then register a typed wrapper with `@mcp.tool()` in
`server.py`. For a new routing provider, extend the backend selection in
`routing.py` and return comparable durations, distances, and provenance.
Use WGS84 coordinates at the GeoJSON boundary and `[longitude, latitude]`
for GeoJSON positions.

## Provider configuration

- `SRM_ROUTING_BACKEND=valhalla` is the default. It uses the hosted router at
  `VALHALLA_URL`, which defaults to the public FOSSGIS instance.
- `SRM_ROUTING_BACKEND=osmnx` uses a local graph. Install the optional
  dependencies with `.venv/bin/python -m pip install '.[routing]'`.
  Graph creation downloads OSM data. Cached graphs live under
  `${SRM_CACHE:-.cache}/graphs`. This backend suits small areas and computes
  travel time from a configured speed for each mode.
- `NOMINATIM_URL` and `NOMINATIM_USER_AGENT` configure place lookup. Follow the
  public provider's [usage policy](https://operations.osmfoundation.org/policies/nominatim/)
  when using the default endpoint.

Set these in the MCP client's server environment. Routing errors are returned
to the client so it can report the failure or revise the request.

## References and development

The official MCP tutorial shows how to register typed tools and launch a local
stdio server. Amap's travel example demonstrates composing place search and
route queries into a map users can open. This repository uses the same workflow
shape with OSM providers and adds a timed schedule and calendar export. Amap is
a design reference. The current server ships Valhalla and OSMnx routing.
[MCP server tutorial](https://modelcontextprotocol.io/docs/develop/build-server) ·
[Amap travel-planning example](https://developer.amap.com/api/mcp-server/application-case/travel-planning-case) ·
[Leaflet GeoJSON guide](https://leafletjs.com/examples/geojson/)

```sh
.venv/bin/python -m pip install pytest
.venv/bin/python -m pytest -q
```

See [AGENTS.md](AGENTS.md) for contributor-agent instructions,
[example prompts](examples/queries.md) for more requests, and
[evaluation](eval/README.md) for benchmarks and recorded results.
