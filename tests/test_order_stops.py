"""The ordering claim, tested without a network.

order_stops says the order it returns is optimal for the travel-time matrix it
was given. That claim is about the search, not about any particular router, so
it is checked by substituting a known matrix for the backend call.
"""

import pytest

from spatial_reasoning_mcp import routing
from spatial_reasoning_mcp.provenance import SpatialToolError


@pytest.fixture
def line_network(monkeypatch):
    """Stops on a line, one degree of longitude apart.

    Travel time is proportional to separation, so the shortest route starting
    at the first stop is to walk along the line.
    """

    def fake_matrix(points, mode, buffer_m):
        n = len(points)
        seconds = [[abs(points[i][1] - points[j][1]) * 1000 / routing.SPEEDS_M_PER_S[mode]
                    for j in range(n)] for i in range(n)]
        metres = [[abs(points[i][1] - points[j][1]) * 1000 for j in range(n)] for i in range(n)]
        return seconds, metres, f"test matrix ({mode})"

    monkeypatch.setattr(routing, "_matrix", fake_matrix)


def _stops(order):
    names = {0: "start", 1: "one", 2: "two", 3: "three"}
    return [{"name": names[i], "lat": 0.0, "lon": float(i)} for i in order]


def test_returns_the_optimal_order(line_network):
    out = routing.order_stops(_stops([0, 2, 1, 3]))
    assert out["result"]["order"] == ["start", "one", "two", "three"]


def test_start_is_fixed(line_network):
    out = routing.order_stops(_stops([2, 0, 1, 3]))
    assert out["result"]["order"][0] == "two"
    assert out["params"]["fixed_start"] == "two"


def test_reports_how_many_orderings_were_searched(line_network):
    out = routing.order_stops(_stops([0, 1, 2, 3]))
    assert out["params"]["orderings_evaluated"] == 6  # 3! orderings of the rest


def test_total_time_matches_the_walk_along_the_line(line_network):
    out = routing.order_stops(_stops([0, 1, 2, 3]), mode="walk")
    expected = (3 * 1000 / routing.SPEEDS_M_PER_S["walk"]) / 60
    assert abs(out["result"]["total_minutes"] - expected) < 0.1


def test_result_names_the_backend_that_produced_it(line_network):
    out = routing.order_stops(_stops([0, 1, 2]), mode="bike")
    assert out["params"]["mode"] == "bike"
    assert out["params"]["backend"] == routing.BACKEND
    assert "bike" in out["source"]


def test_route_between_uses_the_same_matrix(line_network):
    out = routing.route_between(0.0, 0.0, 0.0, 2.0, mode="drive")
    assert out["result"]["metres"] == 2000.0
    assert out["params"]["backend"] == routing.BACKEND


def test_unknown_backend_raises(monkeypatch):
    monkeypatch.setattr(routing, "BACKEND", "mapquest-1998")
    with pytest.raises(SpatialToolError, match="valhalla or osmnx"):
        routing._matrix([(0, 0), (0, 1)], "walk", 500)


def test_unknown_mode_raises():
    with pytest.raises(SpatialToolError, match="mode must be one of"):
        routing._matrix([(0, 0), (0, 1)], "teleport", 500)
