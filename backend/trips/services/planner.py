"""
Trip planner: orchestrates geocoding, routing and the HOS simulation into a
single response payload consumed by the React frontend.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from . import routing
from .hos import (
    DRIVING, ON, OFF, SB,
    HOSSimulator, Leg, Segment, build_daily_logs,
    PICKUP_MIN, DROPOFF_MIN,
)

# Default trip start: 8:00 AM local on a fixed reference date so logs are stable.
DEFAULT_START = datetime(2025, 1, 6, 8, 0, 0)

STATUS_LABELS = {OFF: "Off Duty", SB: "Sleeper Berth", DRIVING: "Driving",
                 ON: "On Duty (not driving)"}


def _leg_from_route(name: str, r: dict) -> Leg:
    return Leg(
        name=name,
        distance_miles=r["distance_miles"],
        geometry=r["geometry"],
        cum_miles=r["cum_miles"],
    )


def plan_trip(current_location: str, pickup_location: str,
              dropoff_location: str, current_cycle_used: float,
              start_dt: Optional[datetime] = None) -> dict:
    """Compute the full trip plan. Raises routing.RoutingError on bad input."""
    start_dt = start_dt or DEFAULT_START

    # 1. Geocode the three waypoints.
    cur = routing.geocode(current_location)
    pick = routing.geocode(pickup_location)
    drop = routing.geocode(dropoff_location)

    cur_pt, pick_pt, drop_pt = (cur[0], cur[1]), (pick[0], pick[1]), (drop[0], drop[1])

    # 2. Route the two driving legs.
    leg1_route = routing.route(cur_pt, pick_pt)
    leg2_route = routing.route(pick_pt, drop_pt)
    leg1 = _leg_from_route("Current → Pickup", leg1_route)
    leg2 = _leg_from_route("Pickup → Dropoff", leg2_route)

    # 3. Simulate the trip against the HOS rules.
    sim = HOSSimulator(current_cycle_used, start_dt)

    # Drive to the pickup, then 1 h on duty loading.
    sim.drive_leg(leg1)
    sim.on_duty_task(PICKUP_MIN, "Pickup (loading)", lat=pick_pt[0], lng=pick_pt[1])

    # Drive to the dropoff, then 1 h on duty unloading.
    sim.drive_leg(leg2)
    sim.on_duty_task(DROPOFF_MIN, "Drop-off (unloading)", lat=drop_pt[0], lng=drop_pt[1])

    # 4. Build outputs.
    daily_logs = build_daily_logs(sim.segments, start_dt)
    stops = _extract_stops(sim.segments, start_dt)

    approximate = bool(leg1_route.get("approximate") or leg2_route.get("approximate"))
    total_distance = leg1.distance_miles + leg2.distance_miles
    total_duration_min = sim.t
    driving_min = sum(s.duration_min() for s in sim.segments if s.status == DRIVING)
    on_duty_min = sum(s.duration_min() for s in sim.segments if s.status in (DRIVING, ON))
    off_min = sum(s.duration_min() for s in sim.segments if s.status in (OFF, SB))

    return {
        "inputs": {
            "current_location": current_location,
            "pickup_location": pickup_location,
            "dropoff_location": dropoff_location,
            "current_cycle_used": current_cycle_used,
        },
        "waypoints": {
            "current": {"lat": cur[0], "lng": cur[1], "name": cur[2]},
            "pickup": {"lat": pick[0], "lng": pick[1], "name": pick[2]},
            "dropoff": {"lat": drop[0], "lng": drop[1], "name": drop[2]},
        },
        "route": {
            "legs": [
                {"name": leg1.name, "distance_miles": round(leg1.distance_miles, 1),
                 "geometry": leg1.geometry},
                {"name": leg2.name, "distance_miles": round(leg2.distance_miles, 1),
                 "geometry": leg2.geometry},
            ],
            "total_distance_miles": round(total_distance, 1),
            "approximate": approximate,
        },
        "summary": {
            "total_distance_miles": round(total_distance, 1),
            "total_duration_hours": round(total_duration_min / 60.0, 1),
            "driving_hours": round(driving_min / 60.0, 1),
            "on_duty_hours": round(on_duty_min / 60.0, 1),
            "off_duty_hours": round(off_min / 60.0, 1),
            "num_days": len(daily_logs),
            "num_fuel_stops": sum(1 for s in sim.segments if s.label == "Fueling stop"),
            "start_time": start_dt.strftime("%Y-%m-%d %H:%M"),
            "end_time": (start_dt + timedelta(minutes=sim.t)).strftime("%Y-%m-%d %H:%M"),
            "cycle_used_start": current_cycle_used,
            "cycle_used_end": round(sim.cycle_used / 60.0, 1),
        },
        "stops": stops,
        "daily_logs": daily_logs,
    }


# Which segment labels are "stops" worth marking on the map.
_STOP_TYPES = {
    "Pickup (loading)": "pickup",
    "Drop-off (unloading)": "dropoff",
    "Fueling stop": "fuel",
    "30-minute break": "break",
    "10-hour off-duty (reset)": "rest",
    "34-hour restart (70-hour cycle reset)": "restart",
}


def _extract_stops(segments: list[Segment], start_dt: datetime) -> list[dict]:
    stops = []
    for seg in segments:
        stop_type = _STOP_TYPES.get(seg.label)
        if not stop_type or seg.lat is None:
            continue
        stops.append({
            "type": stop_type,
            "label": seg.label,
            "lat": seg.lat,
            "lng": seg.lng,
            "arrive": (start_dt + timedelta(minutes=seg.start_min)).strftime("%Y-%m-%d %H:%M"),
            "duration_hours": round(seg.duration_min() / 60.0, 2),
        })
    return stops
