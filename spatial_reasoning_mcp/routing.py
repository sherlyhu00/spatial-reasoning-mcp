"""Routing and stop ordering, over two interchangeable backends.

`valhalla` (default) calls a hosted OpenStreetMap router. It answers in
milliseconds and needs no local data, at the cost of depending on a service.

`osmnx` downloads the street network for the area and routes locally. The
first call for an area is slow -- a walking network includes every footpath,
and the cost grows with the square of the radius -- but once the graph is
cached the results are reproducible offline, which matters when a number has
to be defensible later.

Set SRM_ROUTING_BACKEND to choose. Either way the result names which one
produced it, so a travel time can be traced to the router that computed it.
"""

import os
import sys
from itertools import permutations
from pathlib import Path

import httpx

from .provenance import SpatialToolError, result

BACKEND = os.environ.get("SRM_ROUTING_BACKEND", "valhalla")
VALHALLA_URL = os.environ.get("VALHALLA_URL", "https://valhalla1.openstreetmap.de")

# Valhalla's name for each travel mode.
COSTING = {"walk": "pedestrian", "bike": "bicycle", "drive": "auto"}

# Speeds used only by the osmnx backend, which returns distance and needs a
# speed to turn it into time. Stated here because the answer depends on them.
SPEEDS_M_PER_S = {"walk": 1.4, "bike": 4.2, "drive": 11.1}

MAX_STOPS = 8  # exhaustive ordering stays tractable up to 8 stops (5040 orders)

# Margin around the points when the osmnx backend downloads a network.
DEFAULT_BUFFER_M = 500

_graph_cache: dict = {}
_DISK_CACHE = Path(os.environ.get("SRM_CACHE", Path.cwd() / ".cache")) / "graphs"


def _check_mode(mode: str) -> None:
    if mode not in SPEEDS_M_PER_S:
        raise SpatialToolError(f"mode must be one of {sorted(SPEEDS_M_PER_S)}, got {mode!r}")


# --------------------------------------------------------------------------
# Valhalla backend
# --------------------------------------------------------------------------

def _valhalla_matrix(points: list[tuple[float, float]], mode: str):
    """Pairwise travel time and distance from a hosted OSM router."""
    locations = [{"lat": la, "lon": lo} for la, lo in points]
    try:
        r = httpx.post(
            f"{VALHALLA_URL}/sources_to_targets",
            json={"sources": locations, "targets": locations, "costing": COSTING[mode]},
            timeout=30.0,
        )
        r.raise_for_status()
        rows = r.json()["sources_to_targets"]
    except httpx.HTTPError as e:
        raise SpatialToolError(
            f"Valhalla request failed: {e}. No travel time is returned without a router."
        ) from e
    except (KeyError, ValueError) as e:
        raise SpatialToolError(f"Unexpected response from Valhalla: {e}") from e

    n = len(points)
    seconds = [[0.0] * n for _ in range(n)]
    metres = [[0.0] * n for _ in range(n)]
    for i, row in enumerate(rows):
        for j, cell in enumerate(row):
            if cell.get("time") is None:
                raise SpatialToolError(
                    f"No route between stop {i} and stop {j} for mode {mode!r}."
                )
            seconds[i][j] = float(cell["time"])
            metres[i][j] = float(cell["distance"]) * 1000  # Valhalla reports km
    return seconds, metres, f"OpenStreetMap routing via Valhalla ({COSTING[mode]})"


# --------------------------------------------------------------------------
# OSMnx backend
# --------------------------------------------------------------------------

def _require_osmnx():
    try:
        import networkx as nx  # noqa: F401
        import osmnx as ox
    except ImportError as e:
        raise SpatialToolError(
            "The osmnx backend needs osmnx and networkx: pip install osmnx networkx. "
            "No distance is returned without them, by design."
        ) from e
    return ox


def _graph(points: list[tuple[float, float]], mode: str, buffer_m: int):
    """Street network covering the points, cached in memory and on disk."""
    _check_mode(mode)
    ox = _require_osmnx()
    ox.settings.use_cache = True

    from .geometry import distance_between

    centre = (sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points))
    spread = max(
        distance_between(centre[0], centre[1], la, lo)["result"]["metres"] for la, lo in points
    )
    radius = int(spread + buffer_m)
    key = (round(centre[0], 3), round(centre[1], 3), radius, mode)
    if key in _graph_cache:
        return _graph_cache[key], radius

    _DISK_CACHE.mkdir(parents=True, exist_ok=True)
    path = _DISK_CACHE / f"{key[0]}_{key[1]}_{radius}_{mode}.graphml"
    if path.exists():
        _graph_cache[key] = ox.load_graphml(path)
        return _graph_cache[key], radius

    print(
        f"[spatial-reasoning] downloading {mode} network, {radius} m around "
        f"{centre[0]:.4f},{centre[1]:.4f} (first time for this area)",
        file=sys.stderr,
        flush=True,
    )
    graph = ox.graph_from_point(centre, dist=radius, network_type=mode)
    ox.save_graphml(graph, path)
    _graph_cache[key] = graph
    return graph, radius


def _path_metres(graph, a, b) -> float:
    import networkx as nx
    import osmnx as ox

    na = ox.distance.nearest_nodes(graph, a[1], a[0])
    nb = ox.distance.nearest_nodes(graph, b[1], b[0])
    try:
        return nx.shortest_path_length(graph, na, nb, weight="length")
    except nx.NetworkXNoPath as e:
        raise SpatialToolError("No path exists between these points on this network.") from e


def _osmnx_matrix(points: list[tuple[float, float]], mode: str, buffer_m: int):
    graph, radius = _graph(points, mode, buffer_m)
    n = len(points)
    seconds = [[0.0] * n for _ in range(n)]
    metres = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            m = _path_metres(graph, points[i], points[j])
            metres[i][j] = metres[j][i] = m
            seconds[i][j] = seconds[j][i] = m / SPEEDS_M_PER_S[mode]
    return seconds, metres, (
        f"OSM street network via OSMnx (network_type={mode}, radius={radius} m, "
        f"speed={SPEEDS_M_PER_S[mode]} m/s)"
    )


# --------------------------------------------------------------------------
# Backend selection, then the two tools
# --------------------------------------------------------------------------

def _matrix(points: list[tuple[float, float]], mode: str, buffer_m: int):
    """Pairwise travel times and distances, from whichever backend is selected."""
    _check_mode(mode)
    if BACKEND == "valhalla":
        return _valhalla_matrix(points, mode)
    if BACKEND == "osmnx":
        return _osmnx_matrix(points, mode, buffer_m)
    raise SpatialToolError(f"SRM_ROUTING_BACKEND must be valhalla or osmnx, got {BACKEND!r}")


def route_between(
    lat1: float, lon1: float, lat2: float, lon2: float,
    mode: str = "walk", buffer_m: int = DEFAULT_BUFFER_M,
) -> dict:
    """Network distance and travel time between two points."""
    seconds, metres, source = _matrix([(lat1, lon1), (lat2, lon2)], mode, buffer_m)
    return result(
        {"metres": round(metres[0][1], 1), "minutes": round(seconds[0][1] / 60, 1)},
        source=source,
        mode=mode,
        backend=BACKEND,
        from_=[lat1, lon1],
        to=[lat2, lon2],
    )


def order_stops(stops: list[dict], mode: str = "walk", buffer_m: int = DEFAULT_BUFFER_M) -> dict:
    """Visiting order that minimizes total travel time, starting at the first stop.

    The search is exhaustive over orderings of the remaining stops, so the
    answer is optimal for this travel-time matrix rather than a heuristic.
    That is also why MAX_STOPS is small: the point is a guarantee, not scale.
    """
    if not 2 <= len(stops) <= MAX_STOPS:
        raise SpatialToolError(f"order_stops takes between 2 and {MAX_STOPS} stops.")
    points = [(float(s["lat"]), float(s["lon"])) for s in stops]
    names = [s.get("name", f"stop {i}") for i, s in enumerate(stops)]
    seconds, _metres, source = _matrix(points, mode, buffer_m)

    n = len(points)
    best_order, best_seconds = None, float("inf")
    for order in permutations(range(1, n)):
        route = (0,) + order
        total = sum(seconds[route[k]][route[k + 1]] for k in range(n - 1))
        if total < best_seconds:
            best_order, best_seconds = route, total

    return result(
        {"order": [names[i] for i in best_order], "total_minutes": round(best_seconds / 60, 1)},
        source=source,
        mode=mode,
        backend=BACKEND,
        orderings_evaluated=len(list(permutations(range(1, n)))),
        fixed_start=names[0],
    )
