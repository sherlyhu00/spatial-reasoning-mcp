"""Geometric computation that does not need a street network."""

import json
import math
from pathlib import Path

from shapely.geometry import Point, shape

from .provenance import SpatialToolError, result

EARTH_RADIUS_M = 6_371_008.8  # IUGG mean radius


def distance_between(lat1: float, lon1: float, lat2: float, lon2: float) -> dict:
    """Great-circle distance between two points, in metres.

    This is straight-line distance on a sphere. It is a lower bound on any
    travel distance, never the travel distance itself -- use route_between
    when the question is how far someone actually has to go.
    """
    p1, p2 = map(math.radians, (lat1, lat2))
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    metres = 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))
    return result(
        {"metres": round(metres, 1), "kilometres": round(metres / 1000, 3)},
        source="great-circle distance on a sphere (R = 6371008.8 m)",
        from_=[lat1, lon1],
        to=[lat2, lon2],
    )


def point_in_region(lat: float, lon: float, geojson_path: str, name_field: str = "name") -> dict:
    """Which polygon of a GeoJSON layer contains this point.

    The layer is named in the result, so an answer about "which district" can
    be traced to the boundary file that defined the districts.
    """
    path = Path(geojson_path).expanduser()
    if not path.exists():
        raise SpatialToolError(f"GeoJSON layer not found: {path}")
    try:
        layer = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise SpatialToolError(f"{path} is not valid GeoJSON: {e}") from e

    point = Point(lon, lat)
    for feature in layer.get("features", []):
        geom = feature.get("geometry")
        if not geom:
            continue
        if shape(geom).contains(point):
            props = feature.get("properties", {})
            return result(
                {"match": props.get(name_field), "properties": props},
                source=f"polygon layer {path.name}",
                lat=lat,
                lon=lon,
                name_field=name_field,
            )
    return result(
        {"match": None, "properties": {}},
        source=f"polygon layer {path.name}",
        lat=lat,
        lon=lon,
        note="point falls outside every polygon in the layer",
    )
