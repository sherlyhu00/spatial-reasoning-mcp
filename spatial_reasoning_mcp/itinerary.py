"""Build a daily schedule and export it with departure alarms."""

from datetime import datetime, timedelta, timezone
from math import ceil
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from . import routing
from .provenance import SpatialToolError


class Place(BaseModel):
    name: str = Field(min_length=1)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class Stop(Place):
    starts_at: datetime | None = None
    stay_minutes: int = Field(gt=0, le=1440)


def _utc(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise SpatialToolError("Use ISO 8601 timestamps with a UTC offset.")
    return value.astimezone(timezone.utc)


def _escape(value: str) -> str:
    return (value.replace("\\", "\\\\").replace("\r\n", "\n").replace("\r", "\n")
            .replace("\n", "\\n").replace(";", "\\;").replace(",", "\\,"))


def _fold(line: str) -> str:
    chunks = []
    current = ""
    size = 0
    for char in line:
        width = len(char.encode("utf-8"))
        if size + width > 75:
            chunks.append(current)
            current = " "
            size = 1
        current += char
        size += width
    return "\r\n".join([*chunks, current])


def _calendar(items: list[dict], itinerary_id: str, reminder_minutes: int) -> str:
    def stamp(value: str) -> str:
        return _utc(datetime.fromisoformat(value)).strftime("%Y%m%dT%H%M%SZ")

    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Spatial Reasoning MCP//Daily itinerary//EN"]
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for item in items:
        uid = uuid5(NAMESPACE_URL, f"spatial-reasoning-mcp:{itinerary_id}:{item['id']}")
        lines.extend([
            "BEGIN:VEVENT", f"UID:{uid}@spatial-reasoning-mcp", f"DTSTAMP:{now}",
            f"DTSTART:{stamp(item['start'])}", f"DTEND:{stamp(item['end'])}",
            f"SUMMARY:{_escape(item['title'])}", f"LOCATION:{_escape(item['location'])}",
        ])
        if item["type"] == "travel":
            lines.extend([
                "BEGIN:VALARM", f"TRIGGER:-PT{reminder_minutes}M", "ACTION:DISPLAY",
                f"DESCRIPTION:{_escape(item['title'])}", "END:VALARM",
            ])
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(map(_fold, lines)) + "\r\n"


def plan_day(
    itinerary_id: str,
    starts_at: datetime,
    time_zone: str,
    origin: Place,
    stops: list[Stop],
    mode: str = "walk",
    buffer_minutes: int = 10,
    reminder_minutes: int = 5,
) -> dict:
    if not itinerary_id.strip() or not 1 <= len(stops) <= routing.MAX_STOPS:
        raise SpatialToolError("Provide a stable itinerary ID and between one and eight stops.")
    if not 0 <= buffer_minutes <= 120 or not 1 <= reminder_minutes <= 120:
        raise SpatialToolError("Buffer must be 0–120 minutes and reminder 1–120 minutes.")
    routing._check_mode(mode)
    zone = ZoneInfo(time_zone)
    available = _utc(starts_at)
    local_day = available.astimezone(zone).date()
    items = []
    features = []

    def local(value: datetime) -> str:
        return value.astimezone(zone).isoformat()

    for index, stop in enumerate(stops, 1):
        fixed_start = _utc(stop.starts_at) if stop.starts_at is not None else None
        if (origin.lat, origin.lon) == (stop.lat, stop.lon):
            route_minutes, source = 0, "Identical coordinates"
        else:
            route = routing.route_between(origin.lat, origin.lon, stop.lat, stop.lon, mode)
            route_minutes, source = route["result"]["minutes"], route["source"]

        travel = timedelta(minutes=ceil(route_minutes) + buffer_minutes) if route_minutes else timedelta()
        earliest_start = available + travel
        if fixed_start is not None and fixed_start < earliest_start:
            raise SpatialToolError(
                f"Cannot reach {stop.name} by {local(fixed_start)}. Earliest start: {local(earliest_start)}."
            )
        start = fixed_start if fixed_start is not None else earliest_start
        end = start + timedelta(minutes=stop.stay_minutes)
        if start.astimezone(zone).date() != local_day or end.astimezone(zone).date() != local_day:
            raise SpatialToolError(f"{stop.name} falls outside {local_day} in {time_zone}.")
        if travel:
            items.append({
                "id": f"travel-{index}", "type": "travel", "title": f"Depart for {stop.name}",
                "start": local(start - travel), "end": local(start), "location": origin.name,
                "mode": mode, "route_minutes": route_minutes, "buffer_minutes": buffer_minutes,
                "source": source,
            })
        items.append({
            "id": f"stop-{index}", "type": "activity", "title": stop.name,
            "start": local(start), "end": local(end), "location": stop.name,
        })
        features.append({
            "type": "Feature", "geometry": {"type": "Point", "coordinates": [stop.lon, stop.lat]},
            "properties": {"order": index, "name": stop.name, "starts_at": local(start)},
        })
        origin, available = stop, end

    return {
        "itinerary_id": itinerary_id, "time_zone": time_zone, "items": items,
        "geojson": {"type": "FeatureCollection", "features": features},
        "ics": _calendar(items, itinerary_id, reminder_minutes),
    }
