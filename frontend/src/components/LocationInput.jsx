// Combobox location field: instant suggestions from a curated list of major
// US cities, merged with debounced live results from Nominatim. Anything the
// user types remains valid free text — selecting a suggestion is optional.

import { useEffect, useRef, useState } from "react";

const CITIES = [
  "Albuquerque, NM", "Amarillo, TX", "Atlanta, GA", "Austin, TX",
  "Bakersfield, CA", "Baltimore, MD", "Billings, MT", "Birmingham, AL",
  "Boise, ID", "Boston, MA", "Buffalo, NY", "Charlotte, NC",
  "Chattanooga, TN", "Cheyenne, WY", "Chicago, IL", "Cincinnati, OH",
  "Cleveland, OH", "Columbus, OH", "Dallas, TX", "Denver, CO",
  "Des Moines, IA", "Detroit, MI", "El Paso, TX", "Fargo, ND",
  "Flagstaff, AZ", "Fort Worth, TX", "Fresno, CA", "Green Bay, WI",
  "Harrisburg, PA", "Hartford, CT", "Houston, TX", "Indianapolis, IN",
  "Jacksonville, FL", "Kansas City, MO", "Knoxville, TN", "Laredo, TX",
  "Las Vegas, NV", "Little Rock, AR", "Los Angeles, CA", "Louisville, KY",
  "Lubbock, TX", "Memphis, TN", "Miami, FL", "Milwaukee, WI",
  "Minneapolis, MN", "Nashville, TN", "New Orleans, LA", "New York, NY",
  "Newark, NJ", "Oklahoma City, OK", "Omaha, NE", "Orlando, FL",
  "Philadelphia, PA", "Phoenix, AZ", "Pittsburgh, PA", "Portland, OR",
  "Providence, RI", "Raleigh, NC", "Reno, NV", "Richmond, VA",
  "Sacramento, CA", "Salt Lake City, UT", "San Antonio, TX", "San Diego, CA",
  "San Jose, CA", "Savannah, GA", "Seattle, WA", "Sioux Falls, SD",
  "Spokane, WA", "St. Louis, MO", "Tampa, FL", "Toledo, OH",
  "Tucson, AZ", "Tulsa, OK", "Wichita, KS", "Washington, DC",
];

const NOMINATIM = "https://nominatim.openstreetmap.org/search";

export default function LocationInput({ value, onChange, placeholder, dotColor }) {
  const [open, setOpen] = useState(false);
  const [remote, setRemote] = useState([]);
  const [hi, setHi] = useState(-1);
  const boxRef = useRef(null);
  const debounceRef = useRef(null);

  const q = value.trim().toLowerCase();
  const local = q
    ? CITIES.filter((c) => c.toLowerCase().includes(q))
    : CITIES; // untyped focus: browse popular hubs
  const suggestions = [...new Set([...local, ...remote])].slice(0, 8);

  // Debounced live geocoding suggestions (browser-side, key-less).
  useEffect(() => {
    clearTimeout(debounceRef.current);
    if (q.length < 3) {
      setRemote([]);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      try {
        const params = new URLSearchParams({
          q: value, format: "json", limit: "5",
          addressdetails: "1", countrycodes: "us",
        });
        const res = await fetch(`${NOMINATIM}?${params}`);
        if (!res.ok) return;
        const data = await res.json();
        setRemote(
          data
            .map((d) => {
              const a = d.address || {};
              const name = a.city || a.town || a.village || d.name;
              const region = a.state || a.county || "";
              return name ? (region ? `${name}, ${region}` : name) : null;
            })
            .filter(Boolean)
        );
      } catch {
        setRemote([]); // network hiccup → curated list still works
      }
    }, 450);
    return () => clearTimeout(debounceRef.current);
  }, [value, q]);

  // Close on outside click.
  useEffect(() => {
    const onDoc = (e) => {
      if (boxRef.current && !boxRef.current.contains(e.target)) {
        setOpen(false);
        setHi(-1);
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  const pick = (s) => {
    onChange(s);
    setOpen(false);
    setHi(-1);
  };

  const onKeyDown = (e) => {
    if (e.key === "ArrowDown" && !open) {
      setOpen(true);
      return;
    }
    if (!open || !suggestions.length) {
      if (e.key === "Escape") setOpen(false);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHi((h) => Math.min(h + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setHi((h) => Math.max(h - 1, -1));
    } else if (e.key === "Enter" && hi >= 0) {
      e.preventDefault(); // pick instead of submitting the form
      pick(suggestions[hi]);
    } else if (e.key === "Escape") {
      setOpen(false);
      setHi(-1);
    }
  };

  return (
    <div className="input-wrap loc-wrap" ref={boxRef}>
      <span className="dot" style={{ background: dotColor, color: dotColor }} />
      <input
        value={value}
        placeholder={placeholder}
        onChange={(e) => {
          onChange(e.target.value);
          setOpen(true);
          setHi(-1);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
        autoComplete="off"
      />
      {open && suggestions.length > 0 && (
        <ul className="loc-suggest" role="listbox">
          {suggestions.map((s, i) => (
            <li
              key={s}
              role="option"
              aria-selected={i === hi}
              className={`loc-option ${i === hi ? "hi" : ""}`}
              // mousedown (not click) so it fires before the outside-click close
              onMouseDown={(e) => {
                e.preventDefault();
                pick(s);
              }}
              onMouseEnter={() => setHi(i)}
            >
              <span className="loc-pin">📍</span>
              {s}
            </li>
          ))}
          <li className="loc-freetext">
            Or keep typing any address / place — free text works too
          </li>
        </ul>
      )}
    </div>
  );
}
