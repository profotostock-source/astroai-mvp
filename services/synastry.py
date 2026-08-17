"""Synastry calculation engine for Inner Compass Together.

Computes inter-chart aspects between two natal charts, scores them,
and returns a sorted list of synastry aspects.
"""

from __future__ import annotations

import logging
import math

from knowledge.synastry_orbs import ASPECT_ANGLES, ASPECT_WEIGHTS, SYNASTRY_ORBS, TYPE_WEIGHTS

LOGGER = logging.getLogger(__name__)

# All planets considered in synastry (ascendant only if birth_time_known)
PLANETS = ["sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn", "uranus", "neptune", "pluto"]
PERSONAL_PLANETS = ["sun", "moon", "mercury", "venus", "mars"]


def _sign_to_base_degree(sign: str) -> float:
    """Get the base ecliptic degree for a zodiac sign (0=Aries, 30=Taurus, etc.)."""
    sign_order = [
        "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
    ]
    sign_abbr = {
        "Ari": "Aries", "Tau": "Taurus", "Gem": "Gemini", "Can": "Cancer",
        "Leo": "Leo", "Vir": "Virgo", "Lib": "Libra", "Sco": "Scorpio",
        "Sag": "Sagittarius", "Cap": "Capricorn", "Aqu": "Aquarius", "Pis": "Pisces",
    }
    resolved = sign_abbr.get(sign, sign)
    try:
        return float(sign_order.index(resolved)) * 30.0
    except ValueError:
        return 0.0


def get_planet_degree(planet_key: str, chart: dict) -> float | None:
    """Get ecliptic degree (0-360) for a planet from chart data.

    Args:
        planet_key: Lowercase planet name (e.g., "sun", "moon", "ascendant").
        chart: natal chart dict as returned by calculate_natal_chart.

    Returns:
        Ecliptic degree as float in [0, 360), or None if not available.
    """
    # Handle ascendant separately
    if planet_key == "ascendant":
        asc_sign = chart.get("ascendant_sign")
        if not asc_sign or not chart.get("birth_time_known"):
            return None
        # Use first house cusp degree if available
        houses = chart.get("houses", [])
        if houses and isinstance(houses[0], dict):
            try:
                base = _sign_to_base_degree(asc_sign)
                deg = float(houses[0].get("degree", 0))
                return (base + deg) % 360.0
            except (TypeError, ValueError):
                pass
        # Fallback: sign midpoint
        base = _sign_to_base_degree(asc_sign)
        return (base + 15.0) % 360.0

    planets = chart.get("planets", {})
    if isinstance(planets, dict):
        pdata = planets.get(planet_key)
    else:
        # list of dicts with "name" key
        pdata = next((p for p in planets if p.get("name", "").lower() == planet_key), None)

    if pdata is None:
        return None

    sign = pdata.get("sign", "")
    deg_in_sign = float(pdata.get("degree", 0) or 0)
    base = _sign_to_base_degree(sign)
    return (base + deg_in_sign) % 360.0


def _angular_distance(deg_a: float, deg_b: float) -> float:
    """Shortest angular distance between two ecliptic degrees."""
    diff = abs(deg_a - deg_b) % 360.0
    return diff if diff <= 180.0 else 360.0 - diff


def _compute_score(planet_a: str, planet_b: str, aspect: str, orb: float, max_orb: float) -> float:
    """Compute aspect score based on planet importance, aspect type, and orb exactness."""
    # Try both directions for planet weight lookup
    weight = ASPECT_WEIGHTS.get((planet_a, planet_b)) or ASPECT_WEIGHTS.get((planet_b, planet_a)) or 3.0
    type_mod = TYPE_WEIGHTS.get(aspect, 0.7)
    orb_factor = 1.0 - (orb / max_orb)
    return round(weight * type_mod * orb_factor, 3)


def calculate_synastry(chart_a: dict, chart_b: dict) -> list[dict]:
    """Calculate all inter-chart aspects between chart_a and chart_b.

    Args:
        chart_a: Natal chart dict for Person A (from calculate_natal_chart).
        chart_b: Natal chart dict for Person B (from calculate_natal_chart).

    Returns:
        List of aspect dicts sorted by score descending.
        Each dict has: planet_a, planet_b, aspect, orb, angle, score, direction.
    """
    time_a = bool(chart_a.get("birth_time_known", True))
    time_b = bool(chart_b.get("birth_time_known", True))

    # Build planet lists; exclude ascendant if birth time unknown
    planets_a = list(PLANETS)
    planets_b = list(PLANETS)
    if time_a:
        planets_a.append("ascendant")
    if time_b:
        planets_b.append("ascendant")

    aspects_found: list[dict] = []

    for p_a in planets_a:
        deg_a = get_planet_degree(p_a, chart_a)
        if deg_a is None:
            continue

        for p_b in planets_b:
            deg_b = get_planet_degree(p_b, chart_b)
            if deg_b is None:
                continue

            dist = _angular_distance(deg_a, deg_b)

            for aspect_name, exact_angle in ASPECT_ANGLES.items():
                max_orb = SYNASTRY_ORBS.get(aspect_name, 5)
                orb = abs(dist - exact_angle)
                if orb <= max_orb:
                    score = _compute_score(p_a, p_b, aspect_name, orb, max_orb)
                    aspects_found.append({
                        "planet_a": p_a,
                        "planet_b": p_b,
                        "aspect": aspect_name,
                        "orb": round(orb, 2),
                        "angle": float(exact_angle),
                        "score": score,
                        "direction": "a_to_b",
                    })

    # Sort by score descending
    aspects_found.sort(key=lambda x: -x["score"])

    LOGGER.info(
        "Synastry calculation complete: %d aspects found between %s and %s",
        len(aspects_found),
        chart_a.get("name", "A"),
        chart_b.get("name", "B"),
    )
    return aspects_found
