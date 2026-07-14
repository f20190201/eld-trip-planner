"""
Tests for the HOS simulator and trip planner.

The simulator is tested directly with synthetic legs (no network). The planner
is tested with the routing layer monkeypatched so we validate orchestration
and HOS compliance without hitting Nominatim / OSRM.
"""

from datetime import datetime

from django.test import TestCase

from trips.services import hos, planner, routing


def straight_leg(name, miles):
    """A synthetic leg along a line so point_at() works without real geometry."""
    geometry = [(0.0, 0.0), (miles / 69.0, 0.0)]  # ~69 miles per degree lat
    return hos.Leg(name=name, distance_miles=miles,
                   geometry=geometry, cum_miles=[0.0, miles])


class HOSSimulatorTests(TestCase):
    def _run(self, miles, cycle_used=0.0):
        sim = hos.HOSSimulator(cycle_used, datetime(2025, 1, 6, 8, 0))
        sim.drive_leg(straight_leg("leg", miles))
        return sim

    def test_short_trip_no_reset(self):
        """A 200-mile trip fits in one shift with no daily reset."""
        sim = self._run(200)
        assert not any(s.label.startswith("10-hour") for s in sim.segments)
        drive_min = sum(s.duration_min() for s in sim.segments if s.status == hos.DRIVING)
        self.assertAlmostEqual(drive_min, 200 / 55 * 60, places=1)

    def test_thirty_minute_break_after_8h(self):
        """Driving past 8 h forces a 30-minute break."""
        # 8h @ 55mph = 440 miles; go a bit past so a break is required.
        sim = self._run(500)
        breaks = [s for s in sim.segments if s.label == "30-minute break"]
        self.assertGreaterEqual(len(breaks), 1)
        # No driving stretch exceeds 8h between breaks.
        run = 0.0
        for s in sim.segments:
            if s.status == hos.DRIVING:
                run += s.duration_min()
                self.assertLessEqual(round(run, 3), hos.DRIVE_BEFORE_BREAK_MIN)
            elif s.label == "30-minute break":
                run = 0.0

    def test_eleven_hour_driving_limit(self):
        """Never more than 11 h driving between 10-h resets."""
        sim = self._run(1500)  # long enough to need multiple days
        drive_today = 0.0
        for s in sim.segments:
            if s.status == hos.DRIVING:
                drive_today += s.duration_min()
                self.assertLessEqual(round(drive_today, 3), hos.MAX_DRIVE_MIN + 1e-3)
            elif s.label.startswith("10-hour") or s.label.startswith("34-hour"):
                drive_today = 0.0

    def test_fourteen_hour_window(self):
        """Driving never happens more than 14 h into a duty window."""
        sim = self._run(1500)
        window_start = 0.0
        for s in sim.segments:
            if s.label.startswith("10-hour") or s.label.startswith("34-hour"):
                window_start = s.end_min
            if s.status == hos.DRIVING:
                self.assertLessEqual(s.end_min - window_start, hos.MAX_WINDOW_MIN + 1e-3)

    def test_fuel_stop_every_1000_miles(self):
        """A 2,300-mile trip needs at least two fueling stops."""
        sim = self._run(2300)
        fuels = [s for s in sim.segments if s.label == "Fueling stop"]
        self.assertGreaterEqual(len(fuels), 2)

    def test_seventy_hour_cycle_triggers_restart(self):
        """Starting near the cycle cap forces a 34-hour restart on a long trip."""
        sim = self._run(2500, cycle_used=60.0)
        restarts = [s for s in sim.segments if s.label.startswith("34-hour")]
        self.assertGreaterEqual(len(restarts), 1)

    def test_segments_are_contiguous(self):
        """Segments tile the timeline with no gaps or overlaps."""
        sim = self._run(900)
        for a, b in zip(sim.segments, sim.segments[1:]):
            self.assertAlmostEqual(a.end_min, b.start_min, places=6)


class DailyLogTests(TestCase):
    def test_totals_sum_to_24_or_less_per_day(self):
        sim = hos.HOSSimulator(0.0, datetime(2025, 1, 6, 8, 0))
        sim.drive_leg(straight_leg("leg", 1400))
        logs = hos.build_daily_logs(sim.segments, datetime(2025, 1, 6, 8, 0))
        for day in logs:
            total = sum(day["totals"].values())
            self.assertLessEqual(round(total, 2), 24.01)

    def test_day_numbers_are_sequential(self):
        sim = hos.HOSSimulator(0.0, datetime(2025, 1, 6, 8, 0))
        sim.drive_leg(straight_leg("leg", 1400))
        logs = hos.build_daily_logs(sim.segments, datetime(2025, 1, 6, 8, 0))
        self.assertEqual([d["day_number"] for d in logs], list(range(1, len(logs) + 1)))


class MockRoutingMixin:
    """Monkeypatch geocoding/routing so tests never touch the network."""

    def setUp(self):
        super().setUp()
        self._geocode = routing.geocode
        self._route = routing.route

        def fake_geocode(place):
            table = {
                "chicago": (41.8781, -87.6298, "Chicago, IL"),
                "dallas": (32.7767, -96.7970, "Dallas, TX"),
                "denver": (39.7392, -104.9903, "Denver, CO"),
            }
            key = place.strip().lower()
            return table.get(key, (40.0, -90.0, place))

        def fake_route(start, end):
            miles = routing._haversine_miles(start, end) * 1.2  # road factor
            return {"distance_miles": miles, "duration_hours": miles / 55.0,
                    "geometry": [start, end], "cum_miles": [0.0, miles],
                    "approximate": False}

        planner.routing.geocode = fake_geocode
        planner.routing.route = fake_route

    def tearDown(self):
        planner.routing.geocode = self._geocode
        planner.routing.route = self._route
        super().tearDown()


class PlannerTests(MockRoutingMixin, TestCase):
    def test_plan_trip_structure(self):
        result = planner.plan_trip("Chicago", "Dallas", "Denver", 10.0)
        self.assertIn("summary", result)
        self.assertIn("daily_logs", result)
        self.assertIn("stops", result)
        self.assertGreater(result["summary"]["total_distance_miles"], 0)
        self.assertGreaterEqual(result["summary"]["num_days"], 1)
        # Pickup and dropoff stops must be present.
        types = {s["type"] for s in result["stops"]}
        self.assertIn("pickup", types)
        self.assertIn("dropoff", types)

    def test_pickup_and_dropoff_are_one_hour(self):
        result = planner.plan_trip("Chicago", "Dallas", "Denver", 0.0)
        pickup = next(s for s in result["stops"] if s["type"] == "pickup")
        dropoff = next(s for s in result["stops"] if s["type"] == "dropoff")
        self.assertAlmostEqual(pickup["duration_hours"], 1.0, places=2)
        self.assertAlmostEqual(dropoff["duration_hours"], 1.0, places=2)


class APITests(MockRoutingMixin, TestCase):
    """Exercise the HTTP layer with routing still monkeypatched (no network)."""

    def test_plan_endpoint_persists_and_returns(self):
        from trips.models import Trip

        resp = self.client.post(
            "/api/plan/",
            data={"current_location": "Chicago", "pickup_location": "Dallas",
                  "dropoff_location": "Denver", "current_cycle_used": 10},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("trip_id", body)
        self.assertTrue(Trip.objects.filter(pk=body["trip_id"]).exists())

    def test_plan_endpoint_rejects_bad_cycle(self):
        resp = self.client.post(
            "/api/plan/",
            data={"current_location": "Chicago", "pickup_location": "Dallas",
                  "dropoff_location": "Denver", "current_cycle_used": 90},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
