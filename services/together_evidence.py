"""Evidence builder for Inner Compass Together.

Builds structured context from two natal charts and their synastry aspects.
Pattern follows services/evidence_builder.py.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SIGN_ALIASES = {
    "Ari": "Aries", "Tau": "Taurus", "Gem": "Gemini", "Can": "Cancer",
    "Leo": "Leo", "Vir": "Virgo", "Lib": "Libra", "Sco": "Scorpio",
    "Sag": "Sagittarius", "Cap": "Capricorn", "Aqu": "Aquarius", "Pis": "Pisces",
}

SIGN_UA = {
    "Aries": "Овен", "Taurus": "Телець", "Gemini": "Близнюки", "Cancer": "Рак",
    "Leo": "Лев", "Virgo": "Діва", "Libra": "Терези", "Scorpio": "Скорпіон",
    "Sagittarius": "Стрілець", "Capricorn": "Козоріг", "Aquarius": "Водолій", "Pisces": "Риби",
}

# Theme classification rules: (planet_a, planet_b) -> list of themes
# Keys are unordered pairs — we check both (a,b) and (b,a)
THEME_RULES: dict[tuple[str, str], list[str]] = {
    # attraction
    ("venus", "mars"): ["attraction"],
    ("sun", "venus"): ["attraction"],
    ("mars", "moon"): ["attraction"],
    # emotional
    ("moon", "moon"): ["emotional"],
    ("moon", "sun"): ["emotional"],
    ("moon", "saturn"): ["emotional", "stability"],
    ("moon", "venus"): ["emotional", "love_style"],
    # communication
    ("mercury", "mercury"): ["communication"],
    ("mercury", "sun"): ["communication"],
    ("mercury", "moon"): ["communication"],
    # love style
    ("venus", "venus"): ["love_style"],
    ("venus", "jupiter"): ["love_style"],
    # conflict
    ("mars", "mars"): ["conflict"],
    ("mars", "saturn"): ["conflict"],
    ("sun", "mars"): ["conflict"],
    ("saturn", "moon"): ["conflict", "stability"],
    # stability
    ("saturn", "sun"): ["stability"],
    ("jupiter", "moon"): ["stability", "growth"],
    ("saturn", "venus"): ["stability"],
    # growth
    ("jupiter", "sun"): ["growth"],
    ("jupiter", "venus"): ["growth"],
    ("uranus", "sun"): ["growth"],
    ("uranus", "moon"): ["growth"],
    ("uranus", "venus"): ["growth"],
    ("uranus", "mercury"): ["growth"],
}

ALL_THEMES = ["attraction", "emotional", "communication", "love_style", "conflict", "stability", "growth"]


def _sign(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    return SIGN_ALIASES.get(value, value)


def _person_summary(chart: dict) -> dict:
    """Build a compact summary of one person from their natal chart."""
    sun = _sign(chart.get("sun_sign")) or "Unknown"
    moon = _sign(chart.get("moon_sign")) or "Unknown"
    asc = _sign(chart.get("ascendant_sign")) if chart.get("birth_time_known") else None

    planets = chart.get("planets", {})
    planet_signs = {}
    if isinstance(planets, dict):
        for pname, pdata in planets.items():
            if isinstance(pdata, dict):
                planet_signs[pname] = _sign(pdata.get("sign", "")) or "Unknown"

    return {
        "name": chart.get("name", ""),
        "birth_date": chart.get("birth_date", ""),
        "birthplace": chart.get("birthplace", "") or chart.get("birth_place", ""),
        "sun": sun,
        "moon": moon,
        "ascendant": asc,
        "planet_signs": planet_signs,
    }


def _classify_aspects_to_themes(aspects: list[dict]) -> dict[str, list[dict]]:
    """Classify synastry aspects into thematic buckets."""
    themes: dict[str, list[dict]] = {t: [] for t in ALL_THEMES}

    for asp in aspects:
        p_a = asp.get("planet_a", "")
        p_b = asp.get("planet_b", "")
        pair = (p_a, p_b)
        pair_rev = (p_b, p_a)

        matched_themes = THEME_RULES.get(pair) or THEME_RULES.get(pair_rev) or []

        # For conflict: squares and oppositions with Mars/Saturn are extra relevant
        if not matched_themes:
            if asp.get("aspect") in ("square", "opposition"):
                if "mars" in (p_a, p_b) or "saturn" in (p_a, p_b):
                    matched_themes = ["conflict"]

        for theme in matched_themes:
            if theme in themes:
                themes[theme].append(asp)

    return themes


def build_together_context(
    chart_a: dict,
    chart_b: dict,
    profile_a: dict,
    profile_b: dict,
    synastry: list[dict],
) -> dict:
    """Build structured context for the Together report AI writer.

    Args:
        chart_a: Natal chart for Person A.
        chart_b: Natal chart for Person B.
        profile_a: Profile dict for Person A (name, birth_date, etc.).
        profile_b: Profile dict for Person B.
        synastry: List of synastry aspects from calculate_synastry().

    Returns:
        Structured context dict for AI report generation.
    """
    person_a = _person_summary(chart_a)
    person_b = _person_summary(chart_b)

    # Override name from profile if available
    if profile_a.get("name"):
        person_a["name"] = profile_a["name"]
    if profile_b.get("name"):
        person_b["name"] = profile_b["name"]

    # Top aspects (up to 20 by score)
    strongest = synastry[:20]

    # Theme classification
    themes = _classify_aspects_to_themes(synastry)

    # Limit each theme to top 6 aspects by score
    themes_limited = {t: aspects[:6] for t, aspects in themes.items()}

    return {
        "report_type": "together_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "person_a": person_a,
        "person_b": person_b,
        "birth_time_known_a": bool(chart_a.get("birth_time_known", True)),
        "birth_time_known_b": bool(chart_b.get("birth_time_known", True)),
        "strongest_aspects": strongest,
        "themes": themes_limited,
        "total_aspects": len(synastry),
    }
