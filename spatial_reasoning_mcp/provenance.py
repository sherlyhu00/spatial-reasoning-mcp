"""Every tool returns its answer wrapped with where the answer came from.

The point of this server is that a caller can tell a computed value from a
guess. A bare number cannot be checked; a number with its source and the
parameters that produced it can be.
"""

from typing import Any


def result(value: Any, source: str, **params: Any) -> dict:
    """Wrap a computed value with its provenance.

    value  -- what the tool computed
    source -- the dataset or method it came from, named precisely enough
              that someone could reproduce the call
    params -- the settings that affect the value (mode, radius, units, ...)
    """
    return {"result": value, "source": source, "params": params}


class SpatialToolError(RuntimeError):
    """Raised when a tool cannot compute an answer.

    Deliberately not caught and turned into a default value: a failed lookup
    must reach the agent as a failure, so it does not silently become an
    invented number in the final response.
    """
