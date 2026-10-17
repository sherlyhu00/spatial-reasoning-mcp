"""Latency of each tool, measured where the cost actually is.

Three tools compute locally and cost microseconds. Three make a network call
and cost whatever the service costs. Reporting them together would hide that,
so they are reported separately.

    python eval/latency.py [repeats]
"""

import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spatial_reasoning_mcp import geocode, geometry, routing
from spatial_reasoning_mcp.provenance import SpatialToolError

BENCH = Path(__file__).parent / "benchmark.json"


def timed(label: str, fn, repeats: int) -> None:
    samples, failures = [], 0
    for _ in range(repeats):
        t0 = time.perf_counter()
        try:
            fn()
        except SpatialToolError:
            failures += 1
            continue
        samples.append((time.perf_counter() - t0) * 1000)
    if not samples:
        print(f"{label:34}{'all calls failed':>12}")
        return
    note = f"  ({failures} failed)" if failures else ""
    print(f"{label:34}{statistics.median(samples):9.1f} ms{note}")


def main() -> None:
    repeats = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    if not BENCH.exists():
        sys.exit("No benchmark.json. Run: python eval/make_benchmark.py")
    p = json.loads(BENCH.read_text())["pairs"][0]
    a, b = p["from"], p["to"]

    print(f"median of {repeats} calls\n")
    print("local computation")
    timed("  distance_between", lambda: geometry.distance_between(a["lat"], a["lon"], b["lat"], b["lon"]), repeats)

    print("\nnetwork calls")
    timed("  geocode_place", lambda: geocode.geocode_place(a["query"]), repeats)
    timed("  reverse_geocode", lambda: geocode.reverse_geocode(a["lat"], a["lon"]), repeats)
    timed("  route_between (drive)",
          lambda: routing.route_between(a["lat"], a["lon"], b["lat"], b["lon"], mode="drive"), repeats)
    print(f"\nrouting backend: {routing.BACKEND}")
    print("Nominatim is rate limited to one request per second, which is included above.")


if __name__ == "__main__":
    main()
