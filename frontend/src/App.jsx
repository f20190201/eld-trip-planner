import { useEffect, useState } from "react";
import TripForm from "./components/TripForm.jsx";
import RouteMap from "./components/RouteMap.jsx";
import LogSheet from "./components/LogSheet.jsx";
import { planTrip } from "./api.js";

const STOP_ICONS = {
  pickup: { ico: "📦", bg: "rgba(52,211,153,.14)", color: "#34d399" },
  dropoff: { ico: "🏁", bg: "rgba(248,113,113,.14)", color: "#f87171" },
  fuel: { ico: "⛽", bg: "rgba(251,191,36,.14)", color: "#fbbf24" },
  break: { ico: "☕", bg: "rgba(167,139,250,.14)", color: "#a78bfa" },
  rest: { ico: "🛏", bg: "rgba(148,163,184,.14)", color: "#94a3b8" },
  restart: { ico: "🔄", bg: "rgba(148,163,184,.14)", color: "#94a3b8" },
};

function LoadingCard() {
  // If the request drags on (free-tier backend waking from hibernation),
  // explain the wait instead of leaving the user staring at a spinner.
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), 6000);
    return () => clearTimeout(t);
  }, []);
  return (
    <div className="card loading">
      <div className="load-inner">
        <span className="load-truck">🚛</span>
        <div className="load-road" />
        Geocoding, routing and simulating Hours-of-Service…
        {slow && (
          <div className="cold-hint">
            Still working — the backend runs on a free hosting tier and
            hibernates when idle. The first request of a session can take up
            to a minute while the server wakes up.
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ k, v, unit, ico, color }) {
  return (
    <div className="stat" style={{ "--stat-color": color }}>
      <div className="ico">{ico}</div>
      <div>
        <div className="k">{k}</div>
        <div className="v">
          {v}
          {unit && <small> {unit}</small>}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [trip, setTrip] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("map");
  const [theme, setTheme] = useState(
    () => localStorage.getItem("eld-theme") || "dark"
  );

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("eld-theme", theme);
  }, [theme]);

  const handleSubmit = async (input) => {
    setLoading(true);
    setError("");
    try {
      const result = await planTrip(input);
      setTrip(result);
      setTab("map");
    } catch (e) {
      setError(e.message);
      setTrip(null);
    } finally {
      setLoading(false);
    }
  };

  const s = trip?.summary;

  return (
    <div className="app">
      <header className="topbar">
        <div className="logo">
          <svg width="25" height="25" viewBox="0 0 24 24" fill="none"
               stroke="#1a1206" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M10 17h4V5H2v12h3" />
            <path d="M20 17h2v-3.34a4 4 0 0 0-1.17-2.83L19 9h-5v8h1" />
            <circle cx="7.5" cy="17.5" r="2.5" />
            <circle cx="17.5" cy="17.5" r="2.5" />
          </svg>
        </div>
        <div>
          <h1>ELD Trip Planner</h1>
          <div className="sub">Route planning & Hours-of-Service log generator</div>
        </div>
        <div className="spacer" />
        <div className="badge-hos">Property · 70 hr / 8 day</div>
        <button
          className="theme-toggle"
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          title={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}
          aria-label="Toggle color theme"
        >
          {theme === "dark" ? "☀️" : "🌙"}
        </button>
      </header>

      <div className="container">
        <aside>
          <TripForm onSubmit={handleSubmit} loading={loading} error={error} />
        </aside>

        <main className="results">
          {!trip && !loading && (
            <div className="card empty-state">
              <div>
                <div className="empty-art">🚛</div>
                <div className="empty-road" />
                <h3>Plan a compliant trip</h3>
                <p>
                  Enter your current location, pickup and drop-off points, and how
                  many hours you've already used in your 70-hour cycle. We'll route
                  the trip, insert required fuel and rest stops, and draw your ELD
                  daily logs automatically.
                </p>
              </div>
            </div>
          )}

          {loading && <LoadingCard />}

          {trip && !loading && (
            <>
              <section className="card card-pad">
                <h2>Trip Summary</h2>
                <div className="stats">
                  <Stat k="Distance" v={s.total_distance_miles} unit="mi" ico="🛣️" color="#60a5fa" />
                  <Stat k="Drive time" v={s.driving_hours} unit="h" ico="🕐" color="#f59e0b" />
                  <Stat k="Total trip" v={s.total_duration_hours} unit="h" ico="🧭" color="#34d399" />
                  <Stat k="Days / logs" v={s.num_days} ico="📅" color="#a78bfa" />
                  <Stat k="Fuel stops" v={s.num_fuel_stops} ico="⛽" color="#fbbf24" />
                  <Stat k="Cycle used" v={`${s.cycle_used_start}→${s.cycle_used_end}`} unit="h" ico="⏳" color="#f87171" />
                </div>
                {trip.route.approximate && (
                  <div className="approx-note">
                    ⚠ Live routing service was unavailable, so distances use a
                    great-circle estimate (road factor ×1.2) and the map shows a
                    straight-line path. HOS calculations remain accurate to the
                    estimated mileage.
                  </div>
                )}
              </section>

              <div className="tabs">
                <button className={`tab ${tab === "map" ? "active" : ""}`}
                        onClick={() => setTab("map")}>
                  🗺️ Route & Stops
                </button>
                <button className={`tab ${tab === "logs" ? "active" : ""}`}
                        onClick={() => setTab("logs")}>
                  📋 ELD Logs ({trip.daily_logs.length})
                </button>
              </div>

              {tab === "map" && (
                <>
                  <section className="card card-pad">
                    <RouteMap trip={trip} />
                  </section>
                  <section className="card card-pad">
                    <h2>Stops & Rest Schedule</h2>
                    <div className="stops">
                      {trip.stops.map((stop, i) => {
                        const st = STOP_ICONS[stop.type] || STOP_ICONS.break;
                        return (
                          <div className="stop-row" key={i}>
                            <div className="stop-ico"
                                 style={{ background: st.bg, color: st.color }}>
                              {st.ico}
                            </div>
                            <div className="stop-main">
                              <div className="t">{stop.label}</div>
                              <div className="s">
                                {stop.lat.toFixed(3)}, {stop.lng.toFixed(3)}
                              </div>
                            </div>
                            <div className="stop-time">
                              <b>{stop.arrive.split(" ")[1]}</b>
                              <br />
                              {stop.duration_hours} h · {stop.arrive.split(" ")[0]}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </section>
                </>
              )}

              {tab === "logs" && (
                <section className="card card-pad">
                  <div className="logs-head">
                    <h2 style={{ margin: 0 }}>Driver's Daily Logs</h2>
                    <span className="count">
                      {trip.daily_logs.length} sheet
                      {trip.daily_logs.length > 1 ? "s" : ""} · one per calendar day
                    </span>
                  </div>
                  <div className="log-scroll">
                    {trip.daily_logs.map((day) => (
                      <LogSheet key={day.day_number} day={day} trip={trip} />
                    ))}
                  </div>
                </section>
              )}
            </>
          )}
        </main>
      </div>

      <footer className="footer">
        Built with Django + React · Routing via OSRM &amp; OpenStreetMap ·
        HOS rules per FMCSA 49 CFR §395 (property-carrying, 70 hr / 8 day)
      </footer>
    </div>
  );
}
