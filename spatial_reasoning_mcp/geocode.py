"""Place name <-> coordinates, via OpenStreetMap's Nominatim service."""

import os
import threading
import time

import httpx

from .provenance import SpatialToolError, result

NOMINATIM_URL = os.environ.get("NOMINATIM_URL", "https://nominatim.openstreetmap.org")
USER_AGENT = os.environ.get("NOMINATIM_USER_AGENT", "spatial-reasoning-mcp/0.1")

# Nominatim's usage policy allows at most one request per second from a client.
_lock = threading.Lock()
_last_call = 0.0


def _get(path: str, params: dict) -> list | dict:
    global _last_call
    with _lock:
        wait = 1.0 - (time.monotonic() - _last_call)
        if wait > 0:
            time.sleep(wait)
        _last_call = time.monotonic()
    try:
        r = httpx.get(
            f"{NOMINATIM_URL}/{path}",
            params={**params, "format": "jsonv2"},
            headers={"User-Agent": USER_AGENT},
            timeout=20.0,
        )
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        raise SpatialToolError(f"Nominatim request failed: {e}") from e


def geocode_place(query: str, limit: int = 1) -> dict:
    """Resolve a place name or address to coordinates.

    Returns the top match (or `limit` matches) with the display name
    Nominatim resolved it to, so the caller can see whether the right
    place was found before using the coordinates.
    """
    hits = _get("search", {"q": query, "limit": limit})
    if not hits:
        raise SpatialToolError(f"No place matched {query!r}.")
    places = [
        {
            "name": h["display_name"],
            "lat": float(h["lat"]),
            "lon": float(h["lon"]),
            "type": h.get("type"),
        }
        for h in hits
    ]
    return result(
        places[0] if limit == 1 else places,
        source="OpenStreetMap via Nominatim",
        query=query,
        limit=limit,
    )


def reverse_geocode(lat: float, lon: float) -> dict:
    """Resolve coordinates to the nearest addressable place."""
    hit = _get("reverse", {"lat": lat, "lon": lon})
    if not hit or "display_name" not in hit:
        raise SpatialToolError(f"No place found at ({lat}, {lon}).")
    return result(
        {"name": hit["display_name"], "address": hit.get("address", {})},
        source="OpenStreetMap via Nominatim",
        lat=lat,
        lon=lon,
    )
