"""Build the benchmark: resolve place names once, store their coordinates.

Coordinates are resolved through the server's own geocoder and then frozen in
benchmark.json. Freezing matters: the accuracy numbers must not move because a
geocoding service changed between runs.

    python eval/make_benchmark.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spatial_reasoning_mcp import geocode
from spatial_reasoning_mcp.provenance import SpatialToolError

# Pairs chosen to span scales, from a few hundred metres to intercontinental,
# because a model's recall error is not uniform across distance.
PAIRS = [
    ("Georgia Institute of Technology, Atlanta", "Piedmont Park, Atlanta"),
    ("Georgia Aquarium, Atlanta", "Mercedes-Benz Stadium, Atlanta"),
    ("Hartsfield-Jackson Atlanta International Airport", "Georgia State Capitol, Atlanta"),
    ("Empire State Building, New York", "Statue of Liberty, New York"),
    ("Golden Gate Bridge, San Francisco", "Oakland City Hall, California"),
    ("Big Ben, London", "Heathrow Airport, London"),
    ("Eiffel Tower, Paris", "Palace of Versailles, France"),
    ("Tokyo Station, Japan", "Yokohama Station, Japan"),
    ("The Bund, Shanghai", "Shanghai Hongqiao Railway Station"),
    ("Sydney Opera House", "Bondi Beach, Sydney"),
    ("Brandenburg Gate, Berlin", "Potsdam Hauptbahnhof, Germany"),
    ("Union Station, Chicago", "O'Hare International Airport, Chicago"),
]


def main() -> None:
    out = []
    for a, b in PAIRS:
        try:
            ra = geocode.geocode_place(a)["result"]
            rb = geocode.geocode_place(b)["result"]
        except SpatialToolError as e:
            print(f"skipped {a} / {b}: {e}", file=sys.stderr)
            continue
        out.append({
            "from": {"query": a, "resolved": ra["name"], "lat": ra["lat"], "lon": ra["lon"]},
            "to": {"query": b, "resolved": rb["name"], "lat": rb["lat"], "lon": rb["lon"]},
        })
        print(f"  {a[:38]:40} -> {ra['lat']:.5f},{ra['lon']:.5f}")

    path = Path(__file__).parent / "benchmark.json"
    path.write_text(json.dumps({"pairs": out}, indent=2, ensure_ascii=False))
    print(f"\nwrote {len(out)} pairs to {path}")


if __name__ == "__main__":
    main()
