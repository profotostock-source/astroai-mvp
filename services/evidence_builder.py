"""Build the minimal report_context_v1 contract from natal-chart placements."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from knowledge.evidence_rules import PRACTICAL, RULES

SIGN_ALIASES = {
    "Ari": "Aries", "Tau": "Taurus", "Gem": "Gemini", "Can": "Cancer",
    "Leo": "Leo", "Vir": "Virgo", "Lib": "Libra", "Sco": "Scorpio",
    "Sag": "Sagittarius", "Cap": "Capricorn", "Aqu": "Aquarius", "Pis": "Pisces",
}


def _sign(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    return SIGN_ALIASES.get(value, value)


def _fact_from_rule(factor: str, placement: str, rule: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": rule["id"],
        "title": rule["title"],
        "category": rule["category"],
        "confidence": rule["weight"],
        "statement": rule["statement"],
        "evidence": [{
            "factor": factor,
            "placement": placement,
            "rule_id": rule["rule_id"],
            "weight": rule["weight"],
        }],
        "writer_guidance": {
            "include": True,
            "priority": rule["priority"],
            "avoid_absolute_language": True,
        },
    }


def get_practical_recs(chart: dict[str, Any]) -> dict[str, list[str]]:
    """Return merged career / sport / recovery lists for Sun + Moon + Ascendant.

    Items are deduplicated and ordered: Sun first, then Moon, then Ascendant.
    Only placements that have an entry in PRACTICAL contribute.
    """
    birth_time_known = bool(chart.get("birth_time_known", False))
    placements = [
        ("Sun", _sign(chart.get("sun_sign"))),
        ("Moon", _sign(chart.get("moon_sign"))),
    ]
    if birth_time_known:
        placements.append(("Ascendant", _sign(chart.get("ascendant_sign"))))

    merged: dict[str, list[str]] = {"career": [], "sport": [], "recovery": []}
    seen: dict[str, set[str]] = {"career": set(), "sport": set(), "recovery": set()}

    for factor, placement in placements:
        if not placement:
            continue
        entry = PRACTICAL.get((factor, placement), {})
        for key in ("career", "sport", "recovery"):
            for item in entry.get(key, []):
                if item not in seen[key]:
                    seen[key].add(item)
                    merged[key].append(item)

    return merged


def build_report_context(chart: dict[str, Any]) -> dict[str, Any]:
    """Return a small, deterministic context for the AI writer.

    MVP1 deliberately uses only Sun, Moon and Ascendant rules. Ascendant rules
    are excluded when the birth time is unknown.
    """
    birth_time_known = bool(chart.get("birth_time_known", False))
    placements = [
        ("Sun", _sign(chart.get("sun_sign"))),
        ("Moon", _sign(chart.get("moon_sign"))),
    ]
    if birth_time_known:
        placements.append(("Ascendant", _sign(chart.get("ascendant_sign"))))

    facts: list[dict[str, Any]] = []
    for factor, placement in placements:
        if not placement:
            continue
        for rule in RULES.get((factor, placement), []):
            facts.append(_fact_from_rule(factor, placement, rule))

    facts = [fact for fact in facts if fact["confidence"] >= 0.55]
    facts.sort(key=lambda f: (f["writer_guidance"]["priority"], -f["confidence"], f["id"]))
    facts = facts[:20]

    return {
        "schema_version": "1.0.0",
        "kb_version": "1.0.0",
        "prompt_version": "1.0.0",
        "report": {
            "report_id": str(chart.get("report_id") or f"rep_{uuid4().hex[:12]}"),
            "language": "uk",
            "report_type": "personality",
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
        "person": {
            "name": chart.get("name"),
            "birth_date": chart.get("birth_date"),
            "birth_time": chart.get("birth_time"),
            "birth_place": chart.get("birth_place") or chart.get("birthplace"),
        },
        "chart_summary": {
            "sun_sign": _sign(chart.get("sun_sign")),
            "moon_sign": _sign(chart.get("moon_sign")),
            "ascendant_sign": _sign(chart.get("ascendant_sign")) if birth_time_known else None,
            "birth_time_known": birth_time_known,
        },
        "facts": facts,
    }
