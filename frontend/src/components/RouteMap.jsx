import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap } from "react-leaflet";
import L from "leaflet";
import { useEffect } from "react";

// Marker styling per stop type.
const STOP_STYLE = {
  current: { color: "#60a5fa", glyph: "●", title: "Current location" },
  pickup: { color: "#34d399", glyph: "▲", title: "Pickup" },
  dropoff: { color: "#f87171", glyph: "■", title: "Drop-off" },
  fuel: { color: "#fbbf24", glyph: "⛽", title: "Fuel" },
  break: { color: "#a78bfa", glyph: "☕", title: "30-min break" },
  rest: { color: "#94a3b8", glyph: "🛏", title: "10-hr reset" },
  restart: { color: "#94a3b8", glyph: "🛏", title: "34-hr restart" },
};

function divIcon(type, big = false) {
  const s = STOP_STYLE[type] || STOP_STYLE.break;
  const size = big ? 30 : 24;
  return L.divIcon({
    className: "eld-marker",
    html: `<div style="
      width:${size}px;height:${size}px;border-radius:50%;
      background:${s.color};display:grid;place-items:center;
      border:2.5px solid #0b1220;box-shadow:0 2px 8px rgba(0,0,0,.5);
      font-size:${big ? 14 : 11}px;line-height:1;">${s.glyph}</div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

function FitBounds({ points }) {
  const map = useMap();
  useEffect(() => {
    if (points.length) {
      map.fitBounds(points, { padding: [40, 40] });
    }
  }, [points, map]);
  return null;
}

export default function RouteMap({ trip }) {
  const { waypoints, route, stops } = trip;
  const legLines = route.legs.map((l) => l.geometry.map((p) => [p[0], p[1]]));
  const allPoints = legLines.flat();

  const wpMarkers = [
    { ...waypoints.current, type: "current", name: waypoints.current.name },
    { ...waypoints.pickup, type: "pickup", name: waypoints.pickup.name },
    { ...waypoints.dropoff, type: "dropoff", name: waypoints.dropoff.name },
  ];

  // Only intermediate stops (fuel/break/rest) get their own markers here;
  // pickup/dropoff already shown as waypoints.
  const intermediate = stops.filter((s) => !["pickup", "dropoff"].includes(s.type));

  return (
    <>
      <div className="map-wrap">
        <MapContainer center={[39.5, -98.35]} zoom={4} scrollWheelZoom>
          <TileLayer
            attribution='&copy; OpenStreetMap contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          {legLines.map((line, i) => (
            <Polyline key={i} positions={line}
              pathOptions={{ color: i === 0 ? "#60a5fa" : "#f59e0b", weight: 4, opacity: 0.85 }} />
          ))}

          {wpMarkers.map((m, i) => (
            <Marker key={`wp${i}`} position={[m.lat, m.lng]} icon={divIcon(m.type, true)}>
              <Popup>
                <b>{STOP_STYLE[m.type].title}</b>
                <br />
                {m.name}
              </Popup>
            </Marker>
          ))}

          {intermediate.map((s, i) => (
            <Marker key={`st${i}`} position={[s.lat, s.lng]} icon={divIcon(s.type)}>
              <Popup>
                <b>{s.label}</b>
                <br />
                {s.arrive} · {s.duration_hours} h
              </Popup>
            </Marker>
          ))}

          <FitBounds points={allPoints} />
        </MapContainer>
      </div>

      <div className="map-legend">
        {[
          ["current", "Start"],
          ["pickup", "Pickup"],
          ["dropoff", "Drop-off"],
          ["fuel", "Fuel stop"],
          ["break", "30-min break"],
          ["rest", "10-hr reset"],
        ].map(([type, label]) => (
          <span className="legend-item" key={type}>
            <span className="legend-dot" style={{ background: STOP_STYLE[type].color }} />
            {label}
          </span>
        ))}
      </div>
    </>
  );
}
