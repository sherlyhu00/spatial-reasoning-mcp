"""How far a model's recalled distance is from the computed one.

Ground truth here is not this server's output. It is geopy's geodesic, an
independent implementation of Karney's algorithm on the WGS84 ellipsoid. That
lets the same run report two separate things:

  * the error of a model answering from memory, and
  * the error of this server's own spherical approximation,

so the comparison is not the tool grading itself.

    python eval/accuracy.py                    # tool only
    python eval/accuracy.py --model-answers answers.json   # add a model column

The model file is {"<from query>|<to query>": kilometres, ...}; produce it with
whatever model you want to test, asking only for straight-line distance in km.
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from geopy.distance import geodesic

from spatial_reasoning_mcp import geometry

BENCH = Path(__file__).parent / "benchmark.json"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-answers", type=Path, help="JSON of model-recalled distances in km")
    args = ap.parse_args()

    if not BENCH.exists():
        sys.exit("No benchmark.json. Run: python eval/make_benchmark.py")
    pairs = json.loads(BENCH.read_text())["pairs"]
    model = json.loads(args.model_answers.read_text()) if args.model_answers else {}

    rows, tool_err, model_err, latencies = [], [], [], []
    for p in pairs:
        a, b = p["from"], p["to"]
        truth_km = geodesic((a["lat"], a["lon"]), (b["lat"], b["lon"])).km

        t0 = time.perf_counter()
        tool_km = geometry.distance_between(a["lat"], a["lon"], b["lat"], b["lon"])["result"]["kilometres"]
        latencies.append((time.perf_counter() - t0) * 1000)

        t_pct = abs(tool_km - truth_km) / truth_km * 100
        tool_err.append(t_pct)

        key = f"{a['query']}|{b['query']}"
        m_km = model.get(key)
        m_pct = abs(m_km - truth_km) / truth_km * 100 if m_km is not None else None
        if m_pct is not None:
            model_err.append(m_pct)

        rows.append((a["query"].split(",")[0][:26], truth_km, tool_km, t_pct, m_km, m_pct))

    head = f"{'pair':28}{'truth km':>10}{'tool km':>10}{'tool %':>9}"
    if model:
        head += f"{'model km':>10}{'model %':>9}"
    print(head)
    print("-" * len(head))
    for name, truth, tool, tp, mk, mp in rows:
        line = f"{name:28}{truth:10.2f}{tool:10.2f}{tp:9.3f}"
        if model:
            line += f"{mk:10.2f}{mp:9.1f}" if mk is not None else f"{'-':>10}{'-':>9}"
        print(line)

    print()
    print(f"pairs:                       {len(rows)}")
    print(f"tool  median error:          {statistics.median(tool_err):.3f} %   (spherical vs ellipsoid)")
    print(f"tool  worst error:           {max(tool_err):.3f} %")
    if model_err:
        print(f"model median error:          {statistics.median(model_err):.1f} %   (n = {len(model_err)})")
        print(f"model worst error:           {max(model_err):.1f} %")
        print(f"ratio of medians:            {statistics.median(model_err) / statistics.median(tool_err):.0f}x")
    print(f"tool  median latency:        {statistics.median(latencies):.3f} ms  (local computation)")


if __name__ == "__main__":
    main()
