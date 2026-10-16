"""MCP server: geospatial computation, routing and place resolution as tools.

Each tool is a thin wrapper that passes the call through to one of the
modules in this package and lets SpatialToolError propagate, so a failure
reaches the agent as a failure instead of becoming an invented number.
"""

from mcp.server.mcpserver import MCPServer

from . import geocode, geometry, routing

mcp = MCPServer(
    name="spatial-reasoning",
    instructions=(
        "Use these tools for any claim about distance, travel time, ordering of "
        "places, or coordinates. Each result carries the source it was computed "
        "from. If a tool raises, report the failure rather than supplying a value."
    ),
)


@mcp.tool()
def geocode_place(query: str, limit: int = 1) -> dict:
    """Resolve a place name or address to coordinates (OpenStreetMap)."""
    return geocode.geocode_place(query, limit)


@mcp.tool()
def reverse_geocode(lat: float, lon: float) -> dict:
    """Resolve coordinates to the nearest addressable place (OpenStreetMap)."""
    return geocode.reverse_geocode(lat, lon)


@mcp.tool()
def distance_between(lat1: float, lon1: float, lat2: float, lon2: float) -> dict:
    """Great-circle distance between two points. A lower bound on travel distance."""
    return geometry.distance_between(lat1, lon1, lat2, lon2)


@mcp.tool()
def point_in_region(lat: float, lon: float, geojson_path: str, name_field: str = "name") -> dict:
    """Which polygon of a local GeoJSON layer contains this point."""
    return geometry.point_in_region(lat, lon, geojson_path, name_field)


@mcp.tool()
def route_between(
    lat1: float, lon1: float, lat2: float, lon2: float,
    mode: str = "walk", buffer_m: int = 2000,
) -> dict:
    """Network distance and travel time between two points. mode: walk, bike or drive."""
    return routing.route_between(lat1, lon1, lat2, lon2, mode, buffer_m)


@mcp.tool()
def order_stops(stops: list[dict], mode: str = "walk", buffer_m: int = 2000) -> dict:
    """Optimal visiting order for 2-8 stops, starting from the first.

    stops: [{"name": "...", "lat": 0.0, "lon": 0.0}, ...]
    """
    return routing.order_stops(stops, mode, buffer_m)


def main() -> None:
    mcp.run()
