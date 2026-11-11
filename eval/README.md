# Evaluation

Three questions, three harnesses. Each reports what it measured against, because
a number without its reference is the thing this project exists to avoid.

## What is and is not ground truth

For **distance**, ground truth exists: given two coordinates, the distance is a
mathematical fact. `accuracy.py` computes it with geopy's geodesic, an
independent implementation on the WGS84 ellipsoid, and scores both the model
and this server's spherical approximation against it. Neither grades itself.

For **routing**, there is no absolute truth. A travel time is whatever a router
with a particular network, speed model and turn costs says it is. Any claim here
can only be about agreement between independent routers, not correctness.

For **geocoding**, the same holds. What can be measured is how far a recalled
coordinate sits from a resolvable one, not which is right.

## 1. Accuracy

```bash
python eval/make_benchmark.py     # resolve 12 place pairs once, freeze coordinates
python eval/accuracy.py           # error of the tool against the geodesic
```

To add a model column, ask a model for the straight-line distance in kilometres
for each pair, save as `{"<from query>|<to query>": km, ...}`, and run:

```bash
python eval/accuracy.py --model-answers answers.json
```

The pairs span a few hundred metres to intercontinental, because recall error is
not uniform across scale.

## 2. Latency

```bash
python eval/latency.py 5
```

Local computation and network calls are reported separately. Averaging them
would hide that three of the six tools cost microseconds and three cost a round
trip. Nominatim's one-request-per-second policy is enforced in the client, so it
appears in the geocoding figures.

## 3. Scaling

```bash
python eval/scaling.py
```

The travel-time matrix grows as n² in stops; the ordering search grows as
(n−1)!. Measured against a stub router, so the numbers are this project's own
logic rather than a service's load on the day.

## Reporting

Record the numbers you get in this file with the date and the machine
they came from. A latency figure without a machine, or an accuracy figure
without its reference, is not a result.

## Recorded results

Measured 17 October 2026 on an M-series MacBook Air, routing backend
`valhalla` against the public FOSSGIS instance, client in Shanghai.

**Accuracy of `distance_between`**, 12 pairs from 1 km to 27 km, scored against
geopy's WGS84 geodesic:

| | median error | worst error |
|---|---|---|
| this server | 0.18 % | 0.31 % |
| [MODEL NAME], from memory, no tools | 1.7 % | 13.1 % |

The server's error is the cost of modeling the Earth as a sphere rather than an
ellipsoid. It is now a measured bound rather than an assumption: at 25 km the
worst case is about 75 m. The approximation is kept because it needs no
dependency and no network; anything needing survey accuracy should use a
geodesic.

Three things matter more than the ratio of medians.

The benchmark favors the model. All twelve pairs are world-famous landmarks
whose distances appear repeatedly in text. On ordinary streets or census-tract
centroids the gap would be wider, so 9x is a floor, not a typical figure.

The model's error is unpredictable rather than large. It was 0.2 % on the
Eiffel Tower pair and 13.1 % on the Georgia Tech pair, with nothing in either
answer to say which kind it was. The server's error has a known ceiling.

The model's absolute error barely tracks distance: about 110 m typically and up
to 550 m, whether the question spans 1 km or 27 km. Relative error is therefore
worst at short range, which is the range that first- and last-mile and
itinerary questions live in.

**Latency**, median of five calls:

| tool | median |
|---|---|
| `distance_between` | under 0.1 ms |
| `geocode_place` | 994 ms |
| `reverse_geocode` | 1,031 ms |
| `route_between` | 1,025 ms |

The two geocoding figures are dominated by the one-request-per-second limit the
client enforces for Nominatim, not by the service. The routing figure is a real
round trip to Germany; a nearer or self-hosted Valhalla would cut it.

**Scaling** of `order_stops`, against a stub router so the figure is this
project's own search:

| stops | orderings | search |
|---|---|---|
| 4 | 6 | 0.02 ms |
| 6 | 120 | 0.10 ms |
| 8 | 5,040 | 4.51 ms |

Each additional stop multiplies the search by n−1: nine stops would be 8x the
work of eight, twelve stops 7,920x. The eight-stop limit is where exhaustive
search stops being affordable, and therefore where the word "optimal" would
stop being honest.

**Not measured.** Whether an agent using these tools answers better than one
answering from memory. That needs an end-to-end agent benchmark with a task set
and a definition of correct, which this evaluation does not attempt. What is
measured above is the accuracy of the computation the tools perform, and the
cost of performing it.
