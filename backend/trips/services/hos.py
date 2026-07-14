"""
Hours-of-Service (HOS) trip simulator.

Implements the FMCSA property-carrying driver rules for the 70-hour / 8-day cycle:

  * 11-hour driving limit  -- max 11 h driving after 10 consecutive hours off duty.
  * 14-hour driving window -- may not drive after the 14th hour since coming on duty;
                              off-duty time (other than the 10-h reset) does NOT pause it.
  * 30-minute break        -- required after 8 cumulative hours of driving.
  * 10-hour off-duty reset -- restarts the 11-h and 14-h clocks.
  * 70-hour / 8-day limit  -- may not drive after 70 on-duty hours in 8 days.
  * 34-hour restart        -- resets the 70-hour cycle.

Trip assumptions (from the assessment brief):
  * Property-carrying driver, 70 hrs / 8 days, no adverse driving conditions.
  * Fueling at least once every 1,000 miles.
  * 1 hour on duty for pickup and 1 hour on duty for drop-off.

The simulator walks the trip minute-by-event and emits a flat list of duty-status
segments, each carrying an absolute timestamp, a duty status, a human label and
(where meaningful) a geographic position so the frontend can plot it on the map and
draw the ELD grid.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, List, Optional

# --- Duty statuses (match the four rows on a paper log) ---------------------
OFF = "OFF"   # 1. Off Duty
SB = "SB"     # 2. Sleeper Berth
DRIVING = "D"  # 3. Driving
ON = "ON"     # 4. On Duty (not driving)

# --- Rule constants (minutes unless noted) ---------------------------------
AVG_SPEED_MPH = 55.0
MAX_DRIVE_MIN = 11 * 60
MAX_WINDOW_MIN = 14 * 60
DRIVE_BEFORE_BREAK_MIN = 8 * 60
BREAK_MIN = 30
DAILY_OFF_MIN = 10 * 60
CYCLE_MAX_MIN = 70 * 60
RESTART_MIN = 34 * 60

FUEL_INTERVAL_MILES = 1000.0
FUEL_MIN = 30            # on-duty fueling (assumption)
PICKUP_MIN = 60          # 1 hour on duty
DROPOFF_MIN = 60         # 1 hour on duty

EPS = 1e-6


@dataclass
class Segment:
    status: str
    start_min: float          # minutes from trip start
    end_min: float
    label: str
    lat: Optional[float] = None
    lng: Optional[float] = None

    def duration_min(self) -> float:
        return self.end_min - self.start_min


@dataclass
class Leg:
    """A driving leg with geometry so stops can be geo-located."""
    name: str
    distance_miles: float
    # geometry: list of (lat, lng); cum_miles: cumulative distance at each vertex
    geometry: List[tuple] = field(default_factory=list)
    cum_miles: List[float] = field(default_factory=list)

    def point_at(self, miles_into_leg: float) -> Optional[tuple]:
        """Interpolate a (lat, lng) at a distance along the leg."""
        if not self.geometry:
            return None
        d = max(0.0, min(miles_into_leg, self.distance_miles))
        pts, cum = self.geometry, self.cum_miles
        if d <= cum[0]:
            return pts[0]
        if d >= cum[-1]:
            return pts[-1]
        # binary-ish linear scan (geometries are modest in size)
        for i in range(1, len(cum)):
            if cum[i] >= d:
                span = cum[i] - cum[i - 1]
                frac = 0.0 if span <= EPS else (d - cum[i - 1]) / span
                (lat0, lng0), (lat1, lng1) = pts[i - 1], pts[i]
                return (lat0 + (lat1 - lat0) * frac, lng0 + (lng1 - lng0) * frac)
        return pts[-1]


class HOSSimulator:
    def __init__(self, current_cycle_used_hours: float, start_dt: datetime):
        self.t = 0.0
        self.drive_today = 0.0
        self.window_start = 0.0
        self.drive_since_break = 0.0
        self.cycle_used = max(0.0, current_cycle_used_hours) * 60.0
        self.miles_since_fuel = 0.0
        self.total_miles = 0.0
        self.start_dt = start_dt
        self.segments: List[Segment] = []
        # position bookkeeping for the active leg
        self._leg: Optional[Leg] = None
        self._miles_into_leg = 0.0

    # -- helpers ----------------------------------------------------------
    def window_elapsed(self) -> float:
        return self.t - self.window_start

    def _here(self) -> tuple:
        """Current (lat, lng) based on progress along the active leg."""
        if self._leg is None:
            return (None, None)
        p = self._leg.point_at(self._miles_into_leg)
        return p if p else (None, None)

    def _add(self, status: str, minutes: float, label: str,
             lat=None, lng=None) -> None:
        if minutes <= EPS:
            return
        if lat is None and lng is None:
            lat, lng = self._here()
        self.segments.append(
            Segment(status, self.t, self.t + minutes, label, lat, lng)
        )
        self.t += minutes
        if status in (DRIVING, ON):
            self.cycle_used += minutes
        if status == DRIVING:
            self.drive_today += minutes
            self.drive_since_break += minutes

    # -- rest events ------------------------------------------------------
    def _daily_reset(self, label="10-hour off-duty (reset)") -> None:
        self._add(OFF, DAILY_OFF_MIN, label)
        self.drive_today = 0.0
        self.drive_since_break = 0.0
        self.window_start = self.t

    def _restart(self) -> None:
        self._add(OFF, RESTART_MIN, "34-hour restart (70-hour cycle reset)")
        self.drive_today = 0.0
        self.drive_since_break = 0.0
        self.cycle_used = 0.0
        self.window_start = self.t

    def _break(self) -> None:
        self._add(OFF, BREAK_MIN, "30-minute break")
        self.drive_since_break = 0.0

    # -- on-duty (non-driving) work --------------------------------------
    def on_duty_task(self, minutes: float, label: str,
                     lat=None, lng=None) -> None:
        # A required rest may be needed before we can even start work that
        # precedes more driving; keep the cycle honest.
        if self.cycle_used >= CYCLE_MAX_MIN - EPS:
            self._restart()
        self._add(ON, minutes, label, lat=lat, lng=lng)

    # -- driving ----------------------------------------------------------
    def drive_leg(self, leg: Leg) -> None:
        self._leg = leg
        self._miles_into_leg = 0.0
        remaining = leg.distance_miles

        while remaining > EPS:
            # Mandatory resets, most-restrictive first.
            if self.cycle_used >= CYCLE_MAX_MIN - EPS:
                self._restart()
                continue
            if self.drive_today >= MAX_DRIVE_MIN - EPS or \
               self.window_elapsed() >= MAX_WINDOW_MIN - EPS:
                self._daily_reset()
                continue
            if self.drive_since_break >= DRIVE_BEFORE_BREAK_MIN - EPS:
                self._break()
                continue

            # Minutes we may still drive before hitting a limit.
            avail_min = min(
                MAX_DRIVE_MIN - self.drive_today,
                MAX_WINDOW_MIN - self.window_elapsed(),
                DRIVE_BEFORE_BREAK_MIN - self.drive_since_break,
                CYCLE_MAX_MIN - self.cycle_used,
            )
            avail_miles = avail_min / 60.0 * AVG_SPEED_MPH
            miles_to_fuel = FUEL_INTERVAL_MILES - self.miles_since_fuel
            chunk_miles = min(remaining, avail_miles, miles_to_fuel)

            if chunk_miles <= EPS:
                # A limit is exactly hit; loop will trigger the right reset.
                self.drive_today = max(self.drive_today, MAX_DRIVE_MIN)
                continue

            drive_min = chunk_miles / AVG_SPEED_MPH * 60.0
            self._add(DRIVING, drive_min, "Driving")
            self._miles_into_leg += chunk_miles
            self.miles_since_fuel += chunk_miles
            self.total_miles += chunk_miles
            remaining -= chunk_miles

            # Fuel stop when we cross a 1,000-mile boundary mid-trip.
            if self.miles_since_fuel >= FUEL_INTERVAL_MILES - EPS and remaining > EPS:
                self.on_duty_task(FUEL_MIN, "Fueling stop")
                self.miles_since_fuel = 0.0

        self._miles_into_leg = leg.distance_miles


def _round_to_quarter(dt: datetime) -> datetime:
    """ELD grids are read to the nearest 15 minutes; snap the start time."""
    minute = (dt.minute // 15) * 15
    return dt.replace(minute=minute, second=0, microsecond=0)


def build_daily_logs(segments: List[Segment], start_dt: datetime) -> List[dict]:
    """Split the flat segment stream into per-calendar-day ELD logs."""
    if not segments:
        return []

    day_map: dict[str, dict] = {}

    def day_bucket(abs_dt: datetime) -> dict:
        key = abs_dt.strftime("%Y-%m-%d")
        if key not in day_map:
            day_map[key] = {
                "date": key,
                "segments": [],
                "totals": {OFF: 0.0, SB: 0.0, DRIVING: 0.0, ON: 0.0},
            }
        return day_map[key]

    for seg in segments:
        seg_start = start_dt + timedelta(minutes=seg.start_min)
        seg_end = start_dt + timedelta(minutes=seg.end_min)
        cursor = seg_start
        # Split across midnight boundaries so each day's grid is 0-24h.
        while cursor < seg_end:
            midnight = (cursor + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            slice_end = min(seg_end, midnight)
            bucket = day_bucket(cursor)
            start_h = cursor.hour + cursor.minute / 60 + cursor.second / 3600
            end_h = start_h + (slice_end - cursor).total_seconds() / 3600
            bucket["segments"].append({
                "status": seg.status,
                "start_hour": round(start_h, 4),
                "end_hour": round(min(end_h, 24.0), 4),
                "label": seg.label,
                "lat": seg.lat,
                "lng": seg.lng,
                "clock": cursor.strftime("%H:%M"),
            })
            bucket["totals"][seg.status] += (slice_end - cursor).total_seconds() / 3600
            cursor = slice_end

    logs = []
    for i, key in enumerate(sorted(day_map.keys()), start=1):
        d = day_map[key]
        d["day_number"] = i
        d["totals"] = {k: round(v, 2) for k, v in d["totals"].items()}
        d["total_on_duty"] = round(d["totals"][DRIVING] + d["totals"][ON], 2)
        logs.append(d)
    return logs
