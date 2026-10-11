"""
Weather tool for Mkuu.

Uses the custom Nairobi weather API at weather.neckrone8x.co.ke.
Endpoints (expected):
  GET /weather-full?lat=X&lon=Y    →  forecast data
  GET /weather?city=X              →  current conditions (fallback)
  GET /uv?lat=X&lon=Y              →  UV index
  GET /air?lat=X&lon=Y             →  air quality
  GET /local-alerts?lat=X&lon=Y    →  weather alerts

Geocoding uses Open-Meteo's free geocoding service (no key required).
"""

import asyncio
import re
from typing import Optional, Dict, Any

import httpx

# ─── Optional LLM-based city extraction ───
try:
    from app.llm.ollama_provider import OllamaProvider
    _HAS_OLLAMA = True
except Exception:
    OllamaProvider = None  # type: ignore
    _HAS_OLLAMA = False


# ─────────────────────────────────────────────────────────
#  Config
# ─────────────────────────────────────────────────────────

BASE = "https://weather.neckrone8x.co.ke"
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
DEFAULT_CITY = "Kisumu"

STRONG = [
    "weather", "temperature", "forecast", "uv index", "air quality",
    "aqi", "humidity", "how hot", "how cold", "how warm",
    "hali ya hewa", "joto", "baridi", "ubora wa hewa",
    "hewa", "weather ya", "forecast ya",
]
WEAK = [
    "rain", "raining", "sunny", "cloudy", "hot", "cold", "windy", "snow",
    "mvua", "jua", "upepo", "wingu", "theluji",
    "mvua inanyesha", "jua kali", "kuna joto",
]
LOC_HINTS = [
    " in ", " at ", " here", " outside", " today", " tomorrow",
    " right now", " currently", " this week", " tonight",
    " katika ", " hapa ", " leo", " kesho", " sasa",
    " hivi sasa", " wiki hii",
]

CITY_REGEX = re.compile(
    r"\b(?:in|at|for|near|around|katika|hapa|karibu na)\s+"
    r"([A-Za-z][A-Za-z'\-]+(?:\s+[A-Za-z][A-Za-z'\-]+)?)",
    re.IGNORECASE,
)

TIME_WORDS = {
    "today", "tomorrow", "now", "right", "currently", "tonight",
    "week", "morning", "evening", "afternoon", "night",
    "leo", "kesho", "sasa", "wiki", "asubuhi", "jioni", "usiku",
}
SKIP_WORDS = {
    "a", "an", "the", "my", "your", "his", "her", "its", "our",
    "their", "this", "that", "these", "those", "here", "there",
    "town", "city", "area", "region", "country", "place", "world",
}


# ─────────────────────────────────────────────────────────
#  Detection
# ─────────────────────────────────────────────────────────

def is_weather_question(q: str) -> bool:
    """Return True if the user is asking about weather."""
    ql = q.lower()
    if any(k in ql for k in STRONG):
        return True
    if any(k in ql for k in WEAK) and any(h in ql for h in LOC_HINTS):
        return True
    return False


# ─────────────────────────────────────────────────────────
#  City extraction
# ─────────────────────────────────────────────────────────

def _clean_city(s: str) -> Optional[str]:
    words = s.split()
    while words and words[-1].lower() in TIME_WORDS:
        words.pop()
    city = " ".join(words).strip()
    if not city or city.lower() in SKIP_WORDS:
        return None
    return city


def extract_city_regex(q: str) -> Optional[str]:
    """Extract city name using regex patterns."""
    m = CITY_REGEX.search(q)
    if not m:
        return None
    return _clean_city(m.group(1))


EXTRACT_PROMPT = """Extract the city name from the question.
The question may be in English, Kiswahili, or Sheng.
Reply with ONLY the city name, nothing else. If none, reply NONE.

Q: What's the weather in Nairobi? -> Nairobi
Q: Will it rain in Mombasa tomorrow? -> Mombasa
Q: How hot is it? -> NONE
Q: Hali ya hewa iko aje Kisumu? -> Kisumu
Q: Kuna joto aje Nairobi leo? -> Nairobi
Q: Mvua inanyesha wapi? -> NONE"""


async def extract_city_llm(q: str) -> Optional[str]:
    """Use the local LLM to extract the city name (fallback)."""
    if not _HAS_OLLAMA or OllamaProvider is None:
        return None
    try:
        llm = OllamaProvider(model="llama3.2:1b")
        reply = await llm.chat(
            [
                {"role": "system", "content": EXTRACT_PROMPT},
                {"role": "user", "content": f"Q: {q}"},
            ],
            num_predict=15,
        )
        city = reply.strip().strip(".").strip('"').strip("'")
        if not city or city.upper() == "NONE" or len(city) > 40:
            return None
        return city
    except Exception as e:
        print(f"[weather] LLM extraction failed: {e}")
        return None


# ─────────────────────────────────────────────────────────
#  Geocoding
# ─────────────────────────────────────────────────────────

async def geocode(city: str) -> Optional[Dict[str, Any]]:
    """Resolve a city name into lat/lon using Open-Meteo."""
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(
                GEOCODE_URL, params={"name": city, "count": 1}
            )
            r.raise_for_status()
            results = r.json().get("results", [])
    except Exception as e:
        print(f"[weather] geocode failed for {city}: {e}")
        return None
    if not results:
        return None
    top = results[0]
    return {
        "name": top["name"],
        "country": top.get("country", ""),
        "lat": top["latitude"],
        "lon": top["longitude"],
    }


# ─────────────────────────────────────────────────────────
#  API fetching
# ─────────────────────────────────────────────────────────

async def _fetch(
    c: httpx.AsyncClient, path: str, lat: float, lon: float
) -> Any:
    try:
        r = await c.get(
            f"{BASE}{path}",
            params={"lat": lat, "lon": lon},
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"_error": str(e)}


async def _fetch_by_city(city: str) -> Any:
    """Fallback: fetch current weather by city name."""
    try:
        async with httpx.AsyncClient(timeout=15) as c:
            r = await c.get(
                f"{BASE}/weather", params={"city": city}
            )
            r.raise_for_status()
            return r.json()
    except Exception as e:
        return {"_error": str(e)}


async def fetch_all(lat: float, lon: float, city: str) -> Dict[str, Any]:
    """Fetch all weather data in parallel."""
    async with httpx.AsyncClient() as c:
        weather, uv, air, alerts = await asyncio.gather(
            _fetch(c, "/weather-full", lat, lon),
            _fetch(c, "/uv", lat, lon),
            _fetch(c, "/air", lat, lon),
            _fetch(c, "/local-alerts", lat, lon),
        )

    # If /weather-full failed, fall back to /weather?city=
    if isinstance(weather, dict) and "_error" in weather:
        fallback = await _fetch_by_city(city)
        if not (isinstance(fallback, dict) and "_error" in fallback):
            weather = {"_current_only": fallback}

    return {"weather": weather, "uv": uv, "air": air, "alerts": alerts}


# ─────────────────────────────────────────────────────────
#  Formatting
# ─────────────────────────────────────────────────────────

def _extract_slots(weather: Any):
    """Return the list of forecast slots from various response shapes."""
    if not isinstance(weather, dict):
        return None
    # Shape 1: {"forecast": {"list": [...]}}
    if isinstance(weather.get("forecast"), dict):
        return weather["forecast"].get("list")
    # Shape 2: {"list": [...]}
    if isinstance(weather.get("list"), list):
        return weather["list"]
    return None


def _format_current_flat(w: Dict[str, Any]) -> Optional[str]:
    """
    Format the OpenWeatherMap-style response from /weather?city=.
    Expected keys: main, weather, wind, name, sys
    """
    try:
        main = w.get("main", {})
        weather_list = w.get("weather") or [{}]
        desc = weather_list[0].get("description", "?")
        wind = w.get("wind", {})
        name = w.get("name", "Unknown")
        country = w.get("sys", {}).get("country", "")

        temp = main.get("temp")
        feels = main.get("feels_like")
        humidity = main.get("humidity")
        wind_speed = wind.get("speed")

        parts = [f"Current in {name}, {country}:"]
        if temp is not None:
            parts.append(f"{round(temp)}°C")
        if feels is not None:
            parts.append(f"(feels like {round(feels)}°C)")
        parts.append(f"{desc}")
        if humidity is not None:
            parts.append(f"humidity {humidity}%")
        if wind_speed is not None:
            parts.append(f"wind {wind_speed} m/s")
        return " ".join(parts)
    except Exception:
        return None


def summarize(loc: Dict[str, Any], data: Dict[str, Any]) -> str:
    """Turn all weather data into a clean text summary for the LLM."""
    lines = [
        f"Location: {loc['name']}, {loc['country']} "
        f"(lat {loc['lat']:.3f}, lon {loc['lon']:.3f})"
    ]

    weather = data.get("weather")

    # Handle the "flat" fallback response
    if isinstance(weather, dict) and "_current_only" in weather:
        current = _format_current_flat(weather["_current_only"])
        if current:
            lines.append(current)
        weather = None

    # Handle forecast-shaped response
    slots = _extract_slots(weather)
    if slots:
        cur = slots[0]
        main = cur.get("main", {})
        desc = (cur.get("weather") or [{}])[0].get("description", "?")
        wind = cur.get("wind", {})
        lines.append(
            f"Current ({cur.get('dt_txt', '?')}): "
            f"{main.get('temp', '?')}°C "
            f"(feels like {main.get('feels_like', '?')}°C), "
            f"{desc}, humidity {main.get('humidity', '?')}%, "
            f"wind {wind.get('speed', '?')} m/s"
        )
        next_slots = slots[1:5]
        if next_slots:
            lines.append("Next slots:")
            for s in next_slots:
                t = s.get("main", {}).get("temp", "?")
                d = (s.get("weather") or [{}])[0].get(
                    "description", "?"
                )
                pop = s.get("pop")
                ps = f", {int(pop * 100)}% rain" if pop is not None else ""
                lines.append(
                    f"  - {s.get('dt_txt', '?')[:16]} {d} {t}°C{ps}"
                )

    # UV index
    uv = data.get("uv")
    if isinstance(uv, dict) and "value" in uv:
        lines.append(f"UV index: {uv['value']}")

    # Air quality
    air = data.get("air")
    if isinstance(air, dict) and "aqi" in air:
        comp = air.get("components", {})
        lines.append(
            f"Air: AQI {air['aqi']}, "
            f"PM2.5 {comp.get('pm2_5', '?')}, "
            f"PM10 {comp.get('pm10', '?')}"
        )

    # Alerts
    al = data.get("alerts")
    if isinstance(al, dict):
        alerts_list = al.get("alerts") or []
        if alerts_list:
            names = [
                a.get("event") or a.get("title") or "alert"
                for a in alerts_list[:3]
            ]
            lines.append("Alerts: " + "; ".join(names))
        else:
            lines.append("No active alerts.")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────
#  Public entry point
# ─────────────────────────────────────────────────────────

async def weather_report(question: str) -> Dict[str, Any]:
    """
    Main function called by main.py.
    Returns:
      {
        "ok": bool,
        "location": {"name": str, "country": str, "lat": float, "lon": float},
        "summary": str,
        "error": str | None
      }
    """
    # 1. Extract city: try regex first, then LLM, then default
    city = extract_city_regex(question)
    if not city:
        city = await extract_city_llm(question)
    if not city:
        city = DEFAULT_CITY

    # 2. Geocode
    loc = await geocode(city)
    if not loc:
        return {
            "ok": False,
            "error": f"Could not find location: {city}",
            "location": {"name": city, "country": ""},
            "summary": "",
        }

    # 3. Fetch data
    data = await fetch_all(loc["lat"], loc["lon"], city)

    # 4. Format
    summary = summarize(loc, data)
    if not summary.strip():
        return {
            "ok": False,
            "error": "No weather data returned",
            "location": loc,
            "summary": "",
        }

    return {
        "ok": True,
        "location": loc,
        "summary": summary,
        "error": None,
    }