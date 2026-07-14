# 🚚 ELD Trip Planner

A full-stack app for **property-carrying truck drivers** that turns a few trip
inputs into a **routed map with required stops** and a set of **auto-drawn ELD
(Electronic Logging Device) daily logs** — all compliant with the FMCSA
Hours-of-Service rules (70-hour / 8-day cycle).

Built with **Django + Django REST Framework** (backend) and **React + Vite +
React-Leaflet** (frontend). Routing and geocoding use free, key-less
OpenStreetMap services (OSRM + Nominatim), so there are no API keys to manage.

---

## ✨ What it does

**Inputs**
- Current location
- Pickup location
- Drop-off location
- Current cycle used (hours already spent in the 70-hour / 8-day cycle)

**Outputs**
- **Route map** (Current → Pickup → Drop-off) with markers for every fuel stop,
  30-minute break, and 10-hour reset, plus a live stop-by-stop schedule.
- **ELD daily log sheets** — one drawn grid per calendar day, with the duty
  status line, per-status hour totals, and a remarks/duty-change timeline.
  Long trips automatically produce multiple sheets.

**Trip assumptions (from the brief)**
- Property-carrying driver, 70 hrs / 8 days, no adverse driving conditions.
- Fueling at least once every 1,000 miles.
- 1 hour on duty for pickup and 1 hour on duty for drop-off.
- Average driving speed of 55 mph.

---

## 🧠 Hours-of-Service rules implemented

The core simulator (`backend/trips/services/hos.py`) enforces the FMCSA
property-carrying rules (49 CFR §395):

| Rule | Implementation |
|------|----------------|
| **11-hour driving limit** | No more than 11 h driving after a 10-hour off-duty reset. |
| **14-hour driving window** | No driving beyond the 14th hour of a duty period; off-duty time (other than the 10-h reset) does not extend it. |
| **30-minute break** | Required after 8 cumulative hours of driving. |
| **10-hour reset** | Restarts the 11-h and 14-h clocks. |
| **70-hour / 8-day limit** | No driving after 70 on-duty hours; the input "cycle used" seeds this counter. |
| **34-hour restart** | Resets the 70-hour cycle when it is exhausted mid-trip. |
| **Fueling** | An on-duty fuel stop is inserted every 1,000 miles. |
| **Pickup / Drop-off** | 1 hour on-duty each. |

The simulator emits a flat timeline of duty-status segments, which is then split
at midnight into per-day logs and mapped to geographic stop positions along the
route geometry.

---

## 🏗️ Architecture

```
eld-trip-planner/
├── backend/                     # Django + DRF
│   ├── eldbackend/              # project settings / urls / wsgi
│   ├── trips/
│   │   ├── services/
│   │   │   ├── hos.py           # HOS simulator (the core logic)
│   │   │   ├── routing.py       # Nominatim geocode + OSRM route (+ fallback)
│   │   │   └── planner.py       # orchestrates geocode → route → simulate
│   │   ├── models.py            # Trip (stores inputs + computed plan)
│   │   ├── serializers.py       # input validation
│   │   ├── views.py             # /api/plan, /api/trips, /api/health
│   │   └── tests.py             # 13 tests covering HOS compliance
│   ├── requirements.txt
│   └── render.yaml / Procfile   # deployment
└── frontend/                    # React + Vite
    └── src/
        ├── api.js               # fetch wrapper
        ├── App.jsx              # layout, tabs, summary
        └── components/
            ├── TripForm.jsx     # inputs + example presets
            ├── RouteMap.jsx     # React-Leaflet map + markers
            └── LogSheet.jsx     # SVG ELD grid (the drawn log)
```

### API

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/api/plan/` | Plan a trip; returns route, stops, summary, daily logs. |
| `GET`  | `/api/trips/` | List recent planned trips. |
| `GET`  | `/api/trips/<id>/` | Retrieve a stored trip. |
| `GET`  | `/api/health/` | Health check. |

`POST /api/plan/` body:
```json
{
  "current_location": "Chicago, IL",
  "pickup_location": "St. Louis, MO",
  "dropoff_location": "Dallas, TX",
  "current_cycle_used": 12
}
```

---

## 🚀 Running locally

**Prerequisites:** Python 3.9+ and Node 18+.

### 1. Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver 127.0.0.1:8000
```

### 2. Frontend (in a second terminal)
```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. The Vite dev server proxies `/api` to Django,
so no CORS setup is needed for local development.

### Tests
```bash
cd backend
python manage.py test trips
```

---

## ☁️ Deployment

The recommended split is **frontend on Vercel**, **backend on Render** (Render
handles Django + a persistent process more cleanly than serverless).

### Backend → Render
1. Push this repo to GitHub.
2. On [Render](https://render.com) → **New → Blueprint**, point it at the repo.
   `backend/render.yaml` provisions the web service, runs migrations, collects
   static files, and starts gunicorn.
3. Note the resulting URL, e.g. `https://eld-backend.onrender.com`.

*(SQLite on the free tier is ephemeral — fine here, since every plan is
recomputed on request. Add a Postgres instance if you want stored trips to
persist.)*

### Frontend → Vercel
1. On [Vercel](https://vercel.com) → **New Project**, import the repo and set the
   **root directory** to `frontend`.
2. Add an environment variable **`VITE_API_BASE`** = your Render backend URL.
3. Deploy. `frontend/vercel.json` handles the Vite build and SPA routing.

Make sure the backend allows the frontend origin — the provided `render.yaml`
sets `CORS_ALLOW_ALL_ORIGINS=True` for simplicity; tighten it to your Vercel URL
via `CORS_ALLOWED_ORIGINS` for production.

---

## 🗺️ A note on routing

Routing uses the public **OSRM** demo server and **Nominatim** for geocoding
(both key-less). If OSRM is briefly unreachable or rate-limited, the app
gracefully falls back to a great-circle distance estimate (road factor ×1.2)
and a straight-line map path, flagged in the UI — so trip planning never
hard-fails. HOS calculations remain accurate to the estimated mileage. For
production-grade routing accuracy, swap in an OpenRouteService or Mapbox key in
`routing.py`.

---

## 🧾 Tech stack

- **Backend:** Django 4.2, Django REST Framework, requests, WhiteNoise, gunicorn
- **Frontend:** React 18, Vite 5, React-Leaflet 4, Leaflet
- **Maps/Routing:** OpenStreetMap tiles, OSRM (routing), Nominatim (geocoding)
