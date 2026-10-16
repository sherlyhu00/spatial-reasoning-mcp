"""Call every tool once against live data and print what comes back.

Run from the project root, with the virtualenv active:

    python scripts/smoke.py              # drive network: fast
    python scripts/smoke.py walk         # walking network: slower the first time

The travel mode matters for how long this takes, not for whether it works. A
walking network includes every footpath, so the first download and graph build
for a city neighborhood can take minutes; a driving network over the same area
is far smaller. Both are cached afterwards.

This is not the test suite -- it reaches OpenStreetMap, so it needs a network
connection and it is the quickest way to see that the server's answers are
real. Failures print as failures, which is the intended behavior.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spatial_reasoning_mcp import geocode, geometry, routing
from spatial_reasoning_mcp.provenance import SpatialToolError


def show(label, fn):
    print(f"\n--- {label} ---")
    try:
        out = fn()
    except SpatialToolError as e:
        print(f"  FAILED (by design, if this is the point): {e}")
        return None
    print("  result:", json.dumps(out["result"], ensure_ascii=False))
    print("  source:", out["source"])
    print("  params:", json.dumps(out["params"], ensure_ascii=False))
    return out


def main(mode: str = "drive") -> None:
    print(f"(routing in {mode} mode)")
    gt = show("geocode_place: Georgia Tech",
              lambda: geocode.geocode_place("Georgia Institute of Technology, Atlanta"))
    pp = show("geocode_place: Piedmont Park",
              lambda: geocode.geocode_place("Piedmont Park, Atlanta"))

    show("geocode_place: a place that does not exist",
         lambda: geocode.geocode_place("Atlanta Hyperloop Terminal, Georgia"))

    if gt and pp:
        a, b = gt["result"], pp["result"]
        show("distance_between: straight line",
             lambda: geometry.distance_between(a["lat"], a["lon"], b["lat"], b["lon"]))
        show(f"route_between: along the {mode} network",
             lambda: routing.route_between(a["lat"], a["lon"], b["lat"], b["lon"], mode=mode))
        show("reverse_geocode: back from coordinates",
             lambda: geocode.reverse_geocode(a["lat"], a["lon"]))

    # point_in_region needs a layer; make a throwaway one around Midtown.
    layer = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"name": "test box over Midtown Atlanta"},
            "geometry": {"type": "Polygon", "coordinates": [[
                [-84.42, 33.76], [-84.36, 33.76], [-84.36, 33.80], [-84.42, 33.80], [-84.42, 33.76]
            ]]},
        }],
    }
    with tempfile.NamedTemporaryFile("w", suffix=".geojson", delete=False) as f:
        json.dump(layer, f)
    show("point_in_region: inside the box",
         lambda: geometry.point_in_region(33.78, -84.39, f.name))
    show("point_in_region: outside the box",
         lambda: geometry.point_in_region(40.0, -80.0, f.name))
    Path(f.name).unlink()

    if gt and pp:
        stops = [
            {"name": "Georgia Tech", "lat": gt["result"]["lat"], "lon": gt["result"]["lon"]},
            {"name": "Piedmont Park", "lat": pp["result"]["lat"], "lon": pp["result"]["lon"]},
            {"name": "Midtown MARTA", "lat": 33.7806, "lon": -84.3863},
        ]
        show(f"order_stops: three stops, {mode} mode",
             lambda: routing.order_stops(stops, mode=mode))

    print("\nDone. Anything marked FAILED is the server refusing to invent a value.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "drive")
