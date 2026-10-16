# Example sessions

Each example shows a question that a model answers badly from memory, and what
the server returns instead. Run them after registering the server with an MCP
client.

## 1. A distance the model would guess

> How far is it from Georgia Tech to Piedmont Park, and how long to walk?

The agent calls `geocode_place` twice, then `route_between` with `mode="walk"`.
The reply carries `source: OSM street network via OSMnx (network_type=walk,
radius=... m)` and the walking speed used, so the minutes can be checked and
recomputed with a different speed.

Compare with `distance_between` on the same two points: the straight-line value
is always smaller. A model answering from memory tends to report something
between the two with no indication of which it meant.

## 2. An ordering the model would assert

> I want to visit the High Museum, the Botanical Garden and Ponce City Market
> this afternoon, starting from Midtown station. What order?

`order_stops` resolves the four locations, builds the walking travel-time
matrix over the street network, and searches all 6 orderings. The result states
`orderings_evaluated`, so "optimal" means something specific rather than
"plausible".

## 3. A lookup that should fail loudly

> Which neighbourhood is 33.78, -84.38 in?

`point_in_region` needs a boundary layer. Without one it raises rather than
naming a neighbourhood from memory. Given a layer, the result names the file
the answer came from.

## 4. A place that does not exist

> Where is the Atlanta Hyperloop Terminal?

`geocode_place` raises `No place matched ...`. The failure reaches the agent,
which is the point: the alternative is a confident set of coordinates.
