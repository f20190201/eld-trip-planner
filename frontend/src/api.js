// Base URL: in dev, Vite proxies /api to Django. In production set
// VITE_API_BASE to the deployed backend origin (e.g. https://api.example.com).
const API_BASE = import.meta.env.VITE_API_BASE || "";

export async function planTrip(input) {
  const res = await fetch(`${API_BASE}/api/plan/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg =
      data.error ||
      (typeof data === "object"
        ? Object.entries(data)
            .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : v}`)
            .join(" · ")
        : "Request failed");
    throw new Error(msg || `Request failed (${res.status})`);
  }
  return data;
}
