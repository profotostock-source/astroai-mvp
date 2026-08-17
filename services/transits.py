"""Calculate planetary transits for the year ahead.

Computes monthly transit positions and finds which natal points are activated
by slow-moving planets (Jupiter, Saturn, Uranus, Neptune, Pluto).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

# Aspect definitions: name, angle, orb
ASPECTS = [
    ("conjunction", 0, 8),
    ("opposition", 180, 8),
    ("trine", 120, 7),
    ("square", 90, 7),
    ("sextile", 60, 5),
]

# Planets to track as transiting (outer = slow, more significant)
TRANSIT_PLANETS = ["Jupiter", "Saturn", "Uranus", "Neptune", "Pluto"]

MONTH_NAMES_UA = {
    1: "Січень", 2: "Лютий", 3: "Березень", 4: "Квітень",
    5: "Травень", 6: "Червень", 7: "Липень", 8: "Серпень",
    9: "Вересень", 10: "Жовтень", 11: "Листопад", 12: "Грудень",
}


def format_month_year_ua(value: date) -> str:
    """Return a locale-independent Ukrainian month and year label."""
    return f"{MONTH_NAMES_UA[value.month]} {value.year}"

# Natal points we care about
NATAL_POINTS = ["sun", "moon", "ascendant", "mercury", "venus", "mars"]

# Sign-to-longitude offset (0° = Aries start)
SIGN_ORDER = [
    "Ari", "Tau", "Gem", "Can", "Leo", "Vir",
    "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis",
]
SIGN_FULL = {
    "Ari": "Ovni", "Tau": "Taurus", "Gem": "Gemini", "Can": "Cancer",
    "Leo": "Leo", "Vir": "Virgo", "Lib": "Libra", "Sco": "Scorpio",
    "Sag": "Sagittarius", "Cap": "Capricorn", "Aqu": "Aquarius", "Pis": "Pisces",
}


def _to_absolute(sign: str, degree: float) -> float:
    """Convert sign + degree to absolute ecliptic longitude (0–360)."""
    idx = SIGN_ORDER.index(sign) if sign in SIGN_ORDER else 0
    return idx * 30.0 + degree


def _angle_diff(a: float, b: float) -> float:
    """Shortest arc between two longitudes."""
    diff = abs(a - b) % 360
    return min(diff, 360 - diff)


def _find_aspect(transit_lon: float, natal_lon: float) -> dict | None:
    """Return the first matching aspect within orb, or None."""
    for name, angle, orb in ASPECTS:
        diff = _angle_diff(transit_lon, natal_lon)
        if abs(diff - angle) <= orb:
            exactness = 1.0 - abs(diff - angle) / orb
            return {"aspect": name, "orb": round(abs(diff - angle), 1), "exactness": exactness}
    return None


def get_transit_positions(year: int, month: int, day: int = 15) -> dict[str, dict]:
    """Return current positions of slow planets for a given date."""
    try:
        from kerykeion import AstrologicalSubject
        s = AstrologicalSubject(
            "Transit", year, month, day, 12, 0,
            lat=50.45, lng=30.52, tz_str="Europe/Kyiv",
        )
        result = {}
        for planet_name in TRANSIT_PLANETS:
            attr = planet_name.lower()
            data = getattr(s, attr, None)
            if data:
                sign = data["sign"]
                pos = float(data["position"])
                result[planet_name] = {
                    "sign": sign,
                    "degree": round(pos, 1),
                    "lon": _to_absolute(sign, pos),
                    "retrograde": bool(data.get("retrograde")),
                }
        return result
    except Exception as e:
        return {}


def _natal_lon(chart: dict, point: str) -> float | None:
    """Extract absolute longitude for a natal point."""
    sign_key = f"{point}_sign"
    deg_key = f"{point}_degree"

    if point == "ascendant":
        sign = chart.get("ascendant_sign")
        # kerykeion stores asc degree differently
        asc_data = chart.get("first_house") or chart.get("ascendant_data")
        if isinstance(asc_data, dict):
            deg = float(asc_data.get("degree", 0) or 0)
        else:
            deg = 0.0
    else:
        planets = chart.get("planets", {})
        p_data = None
        if isinstance(planets, dict):
            p_data = planets.get(point) or planets.get(point.capitalize())
        elif isinstance(planets, list):
            for p in planets:
                if isinstance(p, dict):
                    name = str(p.get("name", "")).lower()
                    if name == point.lower():
                        p_data = p
                        break
        if p_data:
            sign = p_data.get("sign", "")
            deg = float(p_data.get("degree", 0) or 0)
        else:
            return None

    if not sign or sign not in SIGN_ORDER:
        return None
    return _to_absolute(sign, deg)


def find_active_transits(
    chart: dict[str, Any],
    start_date: date | None = None,
    months: int = 12,
) -> list[dict]:
    """Find all significant transits over the coming year.

    Returns a list of transit events, each with:
    - planet: transiting planet
    - natal_point: what it aspects
    - aspect: conjunction / trine / square / opposition / sextile
    - peak_month: when the transit is closest
    - theme: career / relationships / health / growth
    - intensity: 1–3
    - description_key: used to look up interpretations
    """
    if start_date is None:
        start_date = date.today()

    # Build natal longitudes once
    natal_lons: dict[str, float] = {}
    for point in NATAL_POINTS:
        lon = _natal_lon(chart, point)
        if lon is not None:
            natal_lons[point] = lon
    # Also add Sun/Moon/Asc from top-level keys if not in planets
    for key, sign_field, deg_field in [
        ("sun", "sun_sign", None),
        ("moon", "moon_sign", None),
        ("ascendant", "ascendant_sign", None),
    ]:
        if key not in natal_lons:
            sign = chart.get(sign_field)
            if sign and sign in SIGN_ORDER:
                natal_lons[key] = _to_absolute(sign, 0.0)

    # Sample each month
    seen: dict[str, dict] = {}  # key: planet+point+aspect → best month

    for m in range(months):
        d = start_date + timedelta(days=30 * m)
        positions = get_transit_positions(d.year, d.month, 15)

        for t_planet, t_data in positions.items():
            t_lon = t_data["lon"]
            for n_point, n_lon in natal_lons.items():
                asp = _find_aspect(t_lon, n_lon)
                if asp:
                    key = f"{t_planet}_{n_point}_{asp['aspect']}"
                    if key not in seen or asp["exactness"] > seen[key]["exactness"]:
                        seen[key] = {
                            "planet": t_planet,
                            "natal_point": n_point,
                            "aspect": asp["aspect"],
                            "orb": asp["orb"],
                            "exactness": asp["exactness"],
                            "peak_month": format_month_year_ua(d),
                            "peak_date": d.isoformat(),
                            "retrograde": t_data.get("retrograde", False),
                        }

    # Enrich with theme and intensity
    events = []
    for event in seen.values():
        event = dict(event)
        event["theme"] = _assign_theme(event["planet"], event["natal_point"])
        event["intensity"] = _assign_intensity(event["planet"], event["aspect"])
        event["description_key"] = f"{event['planet'].lower()}_{event['aspect']}_{event['natal_point']}"
        events.append(event)

    events.sort(key=lambda e: (-e["intensity"], e["peak_date"]))
    return events


PLANET_THEME = {
    "Jupiter": ["career", "growth"],
    "Saturn": ["career", "health"],
    "Uranus": ["growth", "relationships"],
    "Neptune": ["growth", "health"],
    "Pluto": ["career", "growth"],
}

POINT_THEME = {
    "sun": "career",
    "moon": "health",
    "ascendant": "relationships",
    "mercury": "career",
    "venus": "relationships",
    "mars": "health",
}

ASPECT_INTENSITY = {
    "conjunction": 3,
    "opposition": 3,
    "square": 2,
    "trine": 2,
    "sextile": 1,
}


def _assign_theme(planet: str, point: str) -> str:
    point_theme = POINT_THEME.get(point, "growth")
    planet_themes = PLANET_THEME.get(planet, ["growth"])
    if point_theme in planet_themes:
        return point_theme
    return planet_themes[0] if planet_themes else "growth"


def _assign_intensity(planet: str, aspect: str) -> int:
    base = ASPECT_INTENSITY.get(aspect, 1)
    if planet in ("Saturn", "Pluto"):
        base = min(base + 1, 3)
    return base


def build_year_context(chart: dict[str, Any], start_date: date | None = None) -> dict[str, Any]:
    """Full year transit context for the AI writer."""
    if start_date is None:
        start_date = date.today()

    events = find_active_transits(chart, start_date, months=12)

    themes: dict[str, list] = {"career": [], "relationships": [], "health": [], "growth": []}
    for ev in events:
        t = ev.get("theme", "growth")
        if t in themes:
            themes[t].append(ev)

    return {
        "period": {
            "start": start_date.strftime("%d.%m.%Y"),
            "end": (start_date + timedelta(days=365)).strftime("%d.%m.%Y"),
        },
        "natal_summary": {
            "sun_sign": chart.get("sun_sign"),
            "moon_sign": chart.get("moon_sign"),
            "ascendant_sign": chart.get("ascendant_sign"),
        },
        "themes": themes,
        "all_events": events,
    }
