"""Tests for the computation that does not depend on a network call.

The geocoding and routing tools reach OpenStreetMap, so they are checked here
only for the behaviour that matters most: that they fail loudly rather than
returning a value when they cannot compute one.
"""

import asyncio
import json
import math
import tempfile
from pathlib import Path

import pytest

from spatial_reasoning_mcp import geometry, routing
from spatial_reasoning_mcp.provenance import SpatialToolError
from spatial_reasoning_mcp.server import mcp


def test_server_exposes_every_tool():
    names = {t.name for t in asyncio.run(mcp.list_tools())}
    assert names == {
        "geocode_place",
        "reverse_geocode",
        "distance_between",
        "point_in_region",
        "route_between",
        "order_stops",
    }


def test_every_result_carries_provenance():
    out = geometry.distance_between(0, 0, 0, 1)
    assert set(out) == {"result", "source", "params"}
    assert out["source"]
    assert out["params"]["to"] == [0, 1]


def test_one_degree_of_longitude_at_the_equator():
    # A degree of longitude at the equator is 2*pi*R/360 metres.
    expected = 2 * math.pi * geometry.EARTH_RADIUS_M / 360
    got = geometry.distance_between(0, 0, 0, 1)["result"]["metres"]
    assert abs(got - expected) < 1.0


def test_pole_to_pole_is_half_the_circumference():
    expected = math.pi * geometry.EARTH_RADIUS_M
    got = geometry.distance_between(90, 0, -90, 0)["result"]["metres"]
    assert abs(got - expected) < 1.0


def test_distance_to_self_is_zero():
    assert geometry.distance_between(33.775, -84.396, 33.775, -84.396)["result"]["metres"] == 0.0


@pytest.fixture
def square_layer():
    layer = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "unit square"},
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]],
                },
            }
        ],
    }
    with tempfile.NamedTemporaryFile("w", suffix=".geojson", delete=False) as f:
        json.dump(layer, f)
    yield f.name
    Path(f.name).unlink()


def test_point_inside_polygon_is_matched(square_layer):
    out = geometry.point_in_region(0.5, 0.5, square_layer)
    assert out["result"]["match"] == "unit square"
    assert "geojson" in out["source"] or square_layer.split("/")[-1] in out["source"]


def test_point_outside_polygon_returns_no_match_not_a_guess(square_layer):
    out = geometry.point_in_region(5, 5, square_layer)
    assert out["result"]["match"] is None
    assert "outside" in out["params"]["note"]


def test_missing_layer_raises_rather_than_answering():
    with pytest.raises(SpatialToolError):
        geometry.point_in_region(0.5, 0.5, "/no/such/layer.geojson")


def test_order_stops_rejects_too_few_and_too_many():
    one = [{"name": "a", "lat": 0, "lon": 0}]
    with pytest.raises(SpatialToolError):
        routing.order_stops(one)
    too_many = [{"name": str(i), "lat": i / 100, "lon": 0} for i in range(routing.MAX_STOPS + 1)]
    with pytest.raises(SpatialToolError):
        routing.order_stops(too_many)


def test_unknown_travel_mode_raises():
    with pytest.raises(SpatialToolError):
        routing._matrix([(0, 0), (0, 0.01)], "teleport", 100)
