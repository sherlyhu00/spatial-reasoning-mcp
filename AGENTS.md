# Instructions for repository agents

Use [README.md](README.md) to set up the stdio server and run the itinerary
example. This file guides agents working in the checkout. MCP clients discover
runtime tools from `spatial_reasoning_mcp/server.py`.

## Develop and verify

- Use Python 3.10 or newer. Create a virtual environment and install the
  package with `python -m pip install -e . pytest`.
- Run `python -m pytest -q` before submitting changes. CI installs the package
  and checks Python 3.10 and 3.11.
- Stub external providers in tests. `scripts/smoke.py` is a separate live
  check that makes network requests.
- Keep MCP wrappers thin and typed. Put calculations and provider calls in
  the matching module. Send stdio server diagnostics to stderr.
- Preserve provider provenance and surface lookup or routing failures as tool
  errors. Update README examples and tool discovery tests when tool names or
  schemas change.
- Keep internal coordinates in WGS84 and export GeoJSON positions in longitude,
  latitude order. Preserve timezone offsets for itinerary inputs.

## Work with itineraries

- Resolve ambiguous places with `geocode_place` before planning. Use
  `route_between` for travel estimates and `distance_between` for straight-line
  distance.
- Pass stops in the intended visiting order with explicit stay durations.
  Preserve fixed appointments and report conflicts raised by `plan_day`.
  Reuse the itinerary ID for revisions of the same ordered itinerary.
- Use the returned `items` for the schedule and the `geojson` for stop markers.
  Use the returned `ics` for calendar import. Describe reminder delivery as
  dependent on calendar import and enabled notifications.
