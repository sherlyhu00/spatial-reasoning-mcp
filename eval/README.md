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

Put the numbers you get in the top-level README with the date and the machine
they came from. A latency figure without a machine, or an accuracy figure
without its reference, is not a result.
