import { useState } from "react";
import LocationInput from "./LocationInput.jsx";

// True when built against a remote backend (e.g. Render free tier) — used to
// warn about cold starts. Local dev proxies to a local Django, so no note.
const REMOTE_API = Boolean(import.meta.env.VITE_API_BASE);

const SAMPLES = [
  {
    label: "Chicago → St. Louis → Dallas",
    current: "Chicago, IL",
    pickup: "St. Louis, MO",
    dropoff: "Dallas, TX",
    cycle: 12,
  },
  {
    label: "Long haul: Los Angeles → Phoenix → Atlanta",
    current: "Los Angeles, CA",
    pickup: "Phoenix, AZ",
    dropoff: "Atlanta, GA",
    cycle: 8,
  },
  {
    label: "Near cycle cap: Denver → Kansas City → Columbus",
    current: "Denver, CO",
    pickup: "Kansas City, MO",
    dropoff: "Columbus, OH",
    cycle: 58,
  },
];

export default function TripForm({ onSubmit, loading, error }) {
  const [form, setForm] = useState({
    current_location: "",
    pickup_location: "",
    dropoff_location: "",
    current_cycle_used: "",
  });

  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const setLoc = (k) => (v) => setForm({ ...form, [k]: v });

  const submit = (e) => {
    e.preventDefault();
    onSubmit({
      ...form,
      current_cycle_used: parseFloat(form.current_cycle_used || "0"),
    });
  };

  const useSample = (s) =>
    setForm({
      current_location: s.current,
      pickup_location: s.pickup,
      dropoff_location: s.dropoff,
      current_cycle_used: String(s.cycle),
    });

  const valid =
    form.current_location && form.pickup_location && form.dropoff_location;

  return (
    <div className="card card-pad">
      <h2>Trip Details</h2>
      <form onSubmit={submit}>
        <div className="form-field">
          <label>Current location</label>
          <LocationInput
            value={form.current_location}
            onChange={setLoc("current_location")}
            placeholder="e.g. Chicago, IL"
            dotColor="#60a5fa"
          />
        </div>

        <div className="form-field">
          <label>Pickup location</label>
          <LocationInput
            value={form.pickup_location}
            onChange={setLoc("pickup_location")}
            placeholder="e.g. St. Louis, MO"
            dotColor="#34d399"
          />
        </div>

        <div className="form-field">
          <label>Drop-off location</label>
          <LocationInput
            value={form.dropoff_location}
            onChange={setLoc("dropoff_location")}
            placeholder="e.g. Dallas, TX"
            dotColor="#f87171"
          />
        </div>

        <div className="form-field">
          <label>
            Current cycle used <span className="hint">(hours, 70-hr / 8-day)</span>
          </label>
          <input
            className="no-dot"
            type="number"
            min="0"
            max="70"
            step="0.5"
            value={form.current_cycle_used}
            onChange={set("current_cycle_used")}
            placeholder="e.g. 12"
          />
        </div>

        <button className="btn-primary" disabled={!valid || loading}>
          {loading ? "Planning route…" : "Plan Trip & Generate Logs"}
        </button>
      </form>

      {error && <div className="error-box">⚠ {error}</div>}

      {REMOTE_API && (
        <div className="cold-note">
          ⚡ <b>Heads up:</b> the backend runs on a free hosting tier and
          hibernates when idle — the first plan of a session may take up to a
          minute while the server wakes up. Subsequent plans are fast.
        </div>
      )}

      <div className="samples">
        <div className="samples-label">Try an example</div>
        {SAMPLES.map((s, i) => (
          <button className="sample-chip" key={i} onClick={() => useSample(s)} type="button">
            {s.label} · <b>{s.cycle}h used</b>
          </button>
        ))}
      </div>
    </div>
  );
}
