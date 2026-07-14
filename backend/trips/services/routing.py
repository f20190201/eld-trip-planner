"""
Geocoding + routing helpers built on free, key-less OpenStreetMap services:

  * Nominatim  -- forward geocoding (place name -> lat/lng).
  * OSRM       -- driving route + geometry between coordinates.

Both are public demo endpoints. They rate-limit aggressively, so results are
cached in-process and every request sends a descriptive User-Agent as their
usage policy requires.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import List, Tuple

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
USER_AGENT = "ELD-Trip-Planner/1.0 (spotter-assessment)"
TIMEOUT = 20

METERS_PER_MILE = 1609.344


class RoutingError(Exception):
    """Raised when geocoding or routing cannot be completed."""


@lru_cache(maxsize=256)
def geocode(place: str) -> Tuple[float, float, str]:
    """Resolve a free-text place to (lat, lng, display_name)."""
    query = (place or "").strip()
    if not query:
        raise RoutingError("Location is empty.")
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": query, "format": "json", "limit": 1,
                    "addressdetails": 0},
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        raise RoutingError(f"Geocoding service unavailable: {exc}") from exc
    if not data:
        raise RoutingError(f"Could not find location: '{place}'.")
    top = data[0]
    return (float(top["lat"]), float(top["lon"]), top.get("display_name", query))


def _haversine_miles(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lat1, lng1, lat2, lng2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    dlat, dlng = lat2 - lat1, lng2 - lng1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 3958.7613 * 2 * math.asin(math.sqrt(h))


# Typical ratio of real road distance to straight-line distance for US
# intercity travel; used only when the routing service is unreachable.
ROAD_FACTOR = 1.2
FALLBACK_SPEED_MPH = 55.0


def _interpolate(start, end, n=48):
    """Evenly spaced points along the straight line between two coords."""
    return [
        (start[0] + (end[0] - start[0]) * i / n,
         start[1] + (end[1] - start[1]) * i / n)
        for i in range(n + 1)
    ]


def _fallback_route(start: Tuple[float, float], end: Tuple[float, float]) -> dict:
    """
    Great-circle estimate used when OSRM is unreachable so the app degrades
    gracefully instead of failing. Distance is scaled by a road factor and the
    geometry is a densified straight line.
    """
    straight = _haversine_miles(start, end)
    distance_miles = straight * ROAD_FACTOR
    geometry = _interpolate(start, end)
    cum, acc = [0.0], 0.0
    for i in range(1, len(geometry)):
        acc += _haversine_miles(geometry[i - 1], geometry[i])
        cum.append(acc)
    if acc > 0:
        scale = distance_miles / acc
        cum = [c * scale for c in cum]
    return {
        "distance_miles": distance_miles,
        "duration_hours": distance_miles / FALLBACK_SPEED_MPH,
        "geometry": geometry,
        "cum_miles": cum,
        "approximate": True,
    }


def route(start: Tuple[float, float], end: Tuple[float, float]) -> dict:
    """
    Driving route between two (lat, lng) points.

    Uses the OSRM public API; if it is unreachable or returns no route, falls
    back to a great-circle estimate so trip planning never hard-fails.

    Returns dict with:
      distance_miles, duration_hours,
      geometry: list of (lat, lng),
      cum_miles: cumulative miles at each geometry vertex,
      approximate: True when the fallback was used.
    """
    coords = f"{start[1]},{start[0]};{end[1]},{end[0]}"
    try:
        resp = requests.get(
            f"{OSRM_URL}/{coords}",
            params={"overview": "full", "geometries": "geojson"},
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException:
        return _fallback_route(start, end)

    if data.get("code") != "Ok" or not data.get("routes"):
        return _fallback_route(start, end)

    r = data["routes"][0]
    # GeoJSON coordinates are [lng, lat]; flip to (lat, lng).
    geometry = [(pt[1], pt[0]) for pt in r["geometry"]["coordinates"]]
    if len(geometry) < 2:
        geometry = [start, end]

    cum, acc = [0.0], 0.0
    for i in range(1, len(geometry)):
        acc += _haversine_miles(geometry[i - 1], geometry[i])
        cum.append(acc)

    distance_miles = r["distance"] / METERS_PER_MILE
    # Scale cumulative distances to OSRM's reported total for consistency.
    if acc > 0:
        scale = distance_miles / acc
        cum = [c * scale for c in cum]

    return {
        "distance_miles": distance_miles,
        "duration_hours": r["duration"] / 3600.0,
        "geometry": geometry,
        "cum_miles": cum,
        "approximate": False,
    }
