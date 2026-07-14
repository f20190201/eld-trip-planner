// Draws a single day's ELD "Driver's Daily Log" grid as SVG: 24 hours across,
// four duty-status rows, the status line, per-row totals and a remarks timeline.

const ROWS = [
  { key: "OFF", label: "1. Off Duty", color: "#475569" },
  { key: "SB", label: "2. Sleeper Berth", color: "#7c3aed" },
  { key: "D", label: "3. Driving", color: "#d97706" },
  { key: "ON", label: "4. On Duty (not driving)", color: "#dc2626" },
];
const ROW_INDEX = { OFF: 0, SB: 1, D: 2, ON: 3 };

const LEFT = 150;
const RIGHT = 62;
const TOP = 26;
const ROW_H = 30;
const HOUR_W = 26;
const GRID_W = HOUR_W * 24;
const W = LEFT + GRID_W + RIGHT;
const H = TOP + ROW_H * 4 + 6;

const xAt = (hour) => LEFT + (hour / 24) * GRID_W;
const rowY = (status) => TOP + ROW_INDEX[status] * ROW_H + ROW_H / 2;

function hourLabel(h) {
  if (h === 0 || h === 24) return "M";
  if (h === 12) return "N";
  return h > 12 ? h - 12 : h;
}

// Fill any uncovered span of the day with Off-Duty so the log accounts for a
// full 24 hours, exactly like a real driver's daily log.
function padDay(segments) {
  const segs = [...segments].sort((a, b) => a.start_hour - b.start_hour);
  const filled = [];
  let cursor = 0;
  for (const s of segs) {
    if (s.start_hour > cursor + 1e-4) {
      filled.push({ status: "OFF", start_hour: cursor, end_hour: s.start_hour, label: "Off duty" });
    }
    filled.push(s);
    cursor = Math.max(cursor, s.end_hour);
  }
  if (cursor < 24 - 1e-4) {
    filled.push({ status: "OFF", start_hour: cursor, end_hour: 24, label: "Off duty" });
  }
  return filled;
}

const ROW_COLOR = Object.fromEntries(ROWS.map((r) => [r.key, r.color]));

function statusLine(segs) {
  // Horizontal runs colored by duty status + neutral vertical connectors at
  // each transition, so the line stays continuous like a real pen trace but
  // each status is identifiable at a glance.
  const runs = [];
  const joins = [];
  let prev = null;
  for (const s of segs) {
    const y = rowY(s.status);
    const x1 = xAt(s.start_hour);
    const x2 = xAt(s.end_hour);
    if (prev && prev.status !== s.status) {
      joins.push({ x: x1, y1: rowY(prev.status), y2: y });
    }
    runs.push({ x1, x2, y, color: ROW_COLOR[s.status] });
    prev = s;
  }
  return { runs, joins };
}

function totalsFrom(segs) {
  const t = { OFF: 0, SB: 0, D: 0, ON: 0 };
  for (const s of segs) t[s.status] += s.end_hour - s.start_hour;
  return t;
}

function remarksFrom(segments) {
  // Collapse consecutive identical labels into a clean duty-change timeline.
  const out = [];
  for (const s of segments) {
    const last = out[out.length - 1];
    if (!last || last.label !== s.label) {
      out.push({ time: s.clock, label: s.label, status: s.status });
    }
  }
  return out;
}

export default function LogSheet({ day, trip }) {
  const padded = padDay(day.segments);
  const totals = totalsFrom(padded);
  const remarks = remarksFrom(day.segments);
  const fmt = (h) => (Math.round(h * 100) / 100).toFixed(2);

  return (
    <div className="logsheet">
      <div className="ls-topline">
        U.S. Department of Transportation · Record of Duty Status · 49 CFR §395.8
      </div>
      <div className="ls-title">
        <h3>Driver's Daily Log</h3>
        <div className="date">
          Day {day.day_number} · {day.date}
        </div>
      </div>

      <div className="ls-meta">
        <div className="m">
          <div className="lbl">From</div>
          <div className="val">{trip.waypoints.current.name.split(",")[0]}</div>
        </div>
        <div className="m">
          <div className="lbl">To</div>
          <div className="val">{trip.waypoints.dropoff.name.split(",")[0]}</div>
        </div>
        <div className="m">
          <div className="lbl">Total Miles (trip)</div>
          <div className="val">{trip.summary.total_distance_miles}</div>
        </div>
        <div className="m">
          <div className="lbl">Carrier</div>
          <div className="val">Spotter Freight Co.</div>
        </div>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img"
           aria-label={`ELD log grid for day ${day.day_number}`}>
        {/* Hour labels */}
        {Array.from({ length: 25 }, (_, h) => (
          <text key={`hl${h}`} x={xAt(h)} y={TOP - 9} textAnchor="middle"
                fontSize="9" fill="#334155" fontWeight="600">
            {hourLabel(h)}
          </text>
        ))}
        <text x={LEFT + GRID_W / 2} y={11} textAnchor="middle" fontSize="8.5"
              fill="#94a3b8" letterSpacing="1.5">HOUR OF DAY</text>

        {/* Row bands + labels + total header */}
        {ROWS.map((r, i) => (
          <g key={r.key}>
            <rect x={LEFT} y={TOP + i * ROW_H} width={GRID_W} height={ROW_H}
                  fill={i % 2 ? "#f1f5f9" : "#ffffff"} />
            <text x={10} y={TOP + i * ROW_H + ROW_H / 2 + 3} fontSize="10"
                  fill="#1f2937" fontWeight="600">{r.label}</text>
            <rect x={4} y={TOP + i * ROW_H + ROW_H / 2 - 5} width={5} height={10}
                  fill={r.color} rx={1} />
          </g>
        ))}

        {/* Vertical hour + quarter-hour ticks */}
        {Array.from({ length: 24 }, (_, h) =>
          [0, 1, 2, 3].map((q) => {
            const x = xAt(h + q / 4);
            const isHour = q === 0;
            return (
              <line key={`t${h}-${q}`} x1={x} y1={TOP} x2={x} y2={TOP + ROW_H * 4}
                    stroke={isHour ? "#94a3b8" : "#e2e8f0"}
                    strokeWidth={isHour ? 1 : 0.5} />
            );
          })
        )}
        <line x1={xAt(24)} y1={TOP} x2={xAt(24)} y2={TOP + ROW_H * 4}
              stroke="#94a3b8" strokeWidth={1} />
        {/* Horizontal separators */}
        {Array.from({ length: 5 }, (_, i) => (
          <line key={`h${i}`} x1={LEFT} y1={TOP + i * ROW_H} x2={LEFT + GRID_W}
                y2={TOP + i * ROW_H} stroke="#334155" strokeWidth={i === 0 || i === 4 ? 1.3 : 0.7} />
        ))}

        {/* Totals column */}
        <text x={LEFT + GRID_W + RIGHT / 2} y={TOP - 9} textAnchor="middle"
              fontSize="8.5" fill="#94a3b8" letterSpacing="0.5">TOTAL</text>
        {ROWS.map((r, i) => (
          <text key={`tot${r.key}`} x={LEFT + GRID_W + RIGHT / 2}
                y={TOP + i * ROW_H + ROW_H / 2 + 4} textAnchor="middle"
                fontSize="12" fontWeight="700" fill={r.color}>
            {fmt(totals[r.key])}
          </text>
        ))}

        {/* Duty status line: colored horizontal runs + neutral connectors */}
        {(() => {
          const { runs, joins } = statusLine(padded);
          return (
            <g>
              {joins.map((j, i) => (
                <line key={`j${i}`} x1={j.x} y1={j.y1} x2={j.x} y2={j.y2}
                      stroke="#64748b" strokeWidth="1.6" />
              ))}
              {runs.map((r, i) => (
                <line key={`r${i}`} x1={r.x1} y1={r.y} x2={r.x2} y2={r.y}
                      stroke={r.color} strokeWidth="3.2" strokeLinecap="round" />
              ))}
            </g>
          );
        })()}
      </svg>

      <div className="ls-recap">
        {ROWS.map((r) => (
          <div className="rc" key={r.key}>
            <span className="swatch" style={{ background: r.color }} />
            <div>
              <div className="rc-k">{r.label.replace(/^\d\.\s/, "")}</div>
              <div className="rc-v">{fmt(totals[r.key])} h</div>
            </div>
          </div>
        ))}
      </div>

      <div className="ls-summary">
        <span>On-duty total: <b>{fmt(totals.D + totals.ON)} h</b></span>
        <span>Off-duty total: <b>{fmt(totals.OFF + totals.SB)} h</b></span>
      </div>

      <div className="ls-remarks">
        <div className="rk-title">Remarks — Duty Status Changes</div>
        {remarks.map((r, i) => (
          <div className="rk" key={i}>
            <span className="rk-time">{r.time}</span>
            <span>{r.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
