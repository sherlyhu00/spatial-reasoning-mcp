"""How cost grows with the size of the question.

Two growth curves matter here, and they are different in kind:

  * the travel-time matrix is O(n^2) in stops, paid once per call;
  * the ordering search is O((n-1)!) in stops, which is why MAX_STOPS is 8.

Both are measured against a stub router, so what is reported is the cost of
this project's own logic rather than of someone's service on the day.

    python eval/scaling.py
"""

import math
import sys
import time
from itertools import permutations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from spatial_reasoning_mcp import routing


def stub_matrix(points, mode, buffer_m):
    """A router that costs nothing, so the measurement is of the search."""
    n = len(points)
    sec = [[abs(points[i][1] - points[j][1]) * 700 for j in range(n)] for i in range(n)]
    return sec, sec, "stub"


def main() -> None:
    real = routing._matrix
    routing._matrix = stub_matrix
    try:
        print(f"{'stops':>6}{'orderings':>12}{'search ms':>12}{'matrix cells':>14}")
        print("-" * 44)
        for n in range(2, routing.MAX_STOPS + 1):
            stops = [{"name": str(i), "lat": 0.0, "lon": i * 0.01} for i in range(n)]
            t0 = time.perf_counter()
            out = routing.order_stops(stops)
            ms = (time.perf_counter() - t0) * 1000
            print(f"{n:6}{out['params']['orderings_evaluated']:12}{ms:12.2f}{n * n:14}")
    finally:
        routing._matrix = real

    print()
    print(f"MAX_STOPS is {routing.MAX_STOPS}. One more stop multiplies the search by n-1:")
    for n in (9, 10, 12):
        factor = math.factorial(n - 1) / math.factorial(routing.MAX_STOPS - 1)
        print(f"  {n:2} stops would be {factor:>8.0f}x the work of {routing.MAX_STOPS}")
    print("\nThis is why the limit is a limit and not a default: past it the exhaustive")
    print("search stops being honest about the word 'optimal'.")


if __name__ == "__main__":
    main()
