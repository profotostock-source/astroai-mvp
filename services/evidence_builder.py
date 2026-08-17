"""Build a traceable, information-rich natal report context."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from knowledge.evidence_rules import PRACTICAL, RULES
from knowledge.natal_rules_v2 import (
    ASPECT_DYNAMICS,
    ELEMENT_LABELS,
    ELEMENTS,
    HOUSE_AREAS,
    MODALITIES,
    MODALITY_LABELS,
    PLANET_DOMAINS,
    RULERS,
    SIGN_STYLES,
)

SIGN_ALIASES = {
    "Ari": "Aries", "Tau": "Taurus", "Gem": "Gemini", "Can": "Cancer",
    "Leo": "Leo", "Vir": "Virgo", "Lib": "Libra", "Sco": "Scorpio",
    "Sag": "Sagittarius", "Cap": "Capricorn", "Aqu": "Aquarius", "Pis": "Pisces",
}
SIGN_ORDER = list(SIGN_STYLES)
POINT_NAMES = {key: label for key, (_, label) in PLANET_DOMAINS.items()}


def _sign(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    return SIGN_ALIASES.get(value, value)


def _evidence_fact(
    fact_id: str,
    title: str,
    category: str,
    statement: str,
    evidence: list[dict[str, Any]],
    confidence: float,
    priority: int,
) -> dict[str, Any]:
    return {
        "id": fact_id,
        "title": title,
        "category": category,
        "confidence": round(confidence, 2),
        "statement": statement,
        "evidence": evidence,
        "writer_guidance": {
            "include": True,
            "priority": priority,
            "avoid_absolute_language": True,
        },
    }


def _fact_from_rule(factor: str, placement: str, rule: dict[str, Any]) -> dict[str, Any]:
    return _evidence_fact(
        rule["id"], rule["title"], rule["category"], rule["statement"],
        [{"factor": factor, "placement": placement, "rule_id": rule["rule_id"], "weight": rule["weight"]}],
        rule["weight"], rule["priority"],
    )


def get_practical_recs(chart: dict[str, Any]) -> dict[str, list[str]]:
    """Return deduplicated practical suggestions for the big three."""
    placements = [("Sun", _sign(chart.get("sun_sign"))), ("Moon", _sign(chart.get("moon_sign")))]
    if chart.get("birth_time_known"):
        placements.append(("Ascendant", _sign(chart.get("ascendant_sign"))))
    merged = {key: [] for key in ("career", "sport", "recovery")}
    for factor, placement in placements:
        for key in merged:
            for item in PRACTICAL.get((factor, placement), {}).get(key, []):
                if item not in merged[key]:
                    merged[key].append(item)
    return merged


def _planet_placement_facts(chart: dict[str, Any]) -> list[dict[str, Any]]:
    facts = []
    for planet, data in chart.get("planets", {}).items():
        if planet not in PLANET_DOMAINS or not isinstance(data, dict):
            continue
        sign = _sign(data.get("sign"))
        if sign not in SIGN_STYLES:
            continue
        domain, label = PLANET_DOMAINS[planet]
        retro = " Ретроградність додає потребу частіше переглядати й осмислювати цю функцію всередині." if data.get("retrograde") else ""
        statement = f"У темах, пов’язаних із {domain}, карта показує {SIGN_STYLES[sign]}.{retro}"
        facts.append(_evidence_fact(
            f"planet_{planet}_{sign.lower()}", f"{label} у знаку {sign}", "placement", statement,
            [{"factor": label, "placement": sign, "degree": data.get("degree"), "retrograde": bool(data.get("retrograde"))}],
            0.78 if planet in {"sun", "moon", "mercury", "venus", "mars"} else 0.66,
            2 if planet in {"sun", "moon", "mercury", "venus", "mars"} else 3,
        ))
    return facts


def _absolute_degree(sign: str | None, degree: Any) -> float | None:
    if sign not in SIGN_ORDER:
        return None
    try:
        return SIGN_ORDER.index(sign) * 30 + float(degree)
    except (TypeError, ValueError):
        return None


def _planet_house(planet_data: dict[str, Any], houses: list[dict[str, Any]]) -> int | None:
    if len(houses) != 12:
        return None
    cusps = [_absolute_degree(_sign(h.get("sign")), h.get("degree")) for h in houses]
    planet = _absolute_degree(_sign(planet_data.get("sign")), planet_data.get("degree"))
    if planet is None or any(cusp is None for cusp in cusps):
        return None
    for index, start in enumerate(cusps):
        end = cusps[(index + 1) % 12]
        span = (end - start) % 360
        if (planet - start) % 360 < span:
            return index + 1
    return None


def _house_facts(chart: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if not chart.get("birth_time_known"):
        return [], {}
    houses = chart.get("houses", [])
    facts, mapping = [], {}
    for planet, data in chart.get("planets", {}).items():
        if planet not in PLANET_DOMAINS or not isinstance(data, dict):
            continue
        house = _planet_house(data, houses)
        if not house:
            continue
        mapping[planet] = house
        domain, label = PLANET_DOMAINS[planet]
        statement = f"Теми {domain} найбільш помітно розгортаються у сфері {HOUSE_AREAS[house]}."
        facts.append(_evidence_fact(
            f"house_{planet}_{house}", f"{label} у {house}-му домі", "house", statement,
            [{"factor": label, "placement": f"house_{house}"}],
            0.74 if planet in {"sun", "moon", "mercury", "venus", "mars", "saturn"} else 0.64,
            2 if planet in {"sun", "moon", "mercury", "venus", "mars", "saturn"} else 3,
        ))
    return facts, mapping


def _aspect_facts(chart: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    for aspect in chart.get("aspects", []):
        if not isinstance(aspect, dict):
            continue
        p1 = str(aspect.get("planet1") or aspect.get("p1_name") or "").lower()
        p2 = str(aspect.get("planet2") or aspect.get("p2_name") or "").lower()
        kind = str(aspect.get("aspect") or "").lower().replace("-", "_").replace(" ", "_")
        kind = {"conjunction": "conjunction", "opposition": "opposition", "square": "square", "trine": "trine", "sextile": "sextile"}.get(kind)
        if p1 not in PLANET_DOMAINS or p2 not in PLANET_DOMAINS or kind not in ASPECT_DYNAMICS:
            continue
        try:
            orb = abs(float(aspect.get("orb", aspect.get("orbit", 99))))
        except (TypeError, ValueError):
            continue
        if orb > 8:
            continue
        candidates.append((orb, p1, p2, kind))
    facts = []
    for orb, p1, p2, kind in sorted(candidates)[:10]:
        domain1, label1 = PLANET_DOMAINS[p1]
        domain2, label2 = PLANET_DOMAINS[p2]
        statement = f"Взаємодія між темами {domain1} та {domain2} {ASPECT_DYNAMICS[kind]}. Орбіс {orb:.1f}° показує силу цього зв’язку в межах обраної системи аспектів."
        facts.append(_evidence_fact(
            f"aspect_{p1}_{kind}_{p2}", f"{label1} — {kind} — {label2}", "aspect", statement,
            [{"factor": f"{label1}-{label2}", "placement": kind, "orb": round(orb, 2)}],
            max(0.6, 0.92 - orb * 0.04), 1 if orb <= 3 else 2,
        ))
    return facts


def _distribution_facts(chart: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    signs = []
    for planet in ("sun", "moon", "mercury", "venus", "mars", "jupiter", "saturn"):
        data = chart.get("planets", {}).get(planet, {})
        sign = _sign(data.get("sign")) if isinstance(data, dict) else None
        if sign in SIGN_STYLES:
            signs.append(sign)
    elements = Counter(ELEMENTS[s] for s in signs)
    modalities = Counter(MODALITIES[s] for s in signs)
    summary = {"elements": dict(elements), "modalities": dict(modalities)}
    facts = []
    if len(signs) >= 5:
        element, count = elements.most_common(1)[0]
        if count >= 3:
            facts.append(_evidence_fact(
                f"dominant_element_{element}", "Провідна стихія", "synthesis",
                f"Серед семи особистих і соціальних планет переважає акцент {ELEMENT_LABELS[element]} ({count} із {len(signs)} позицій). Це повторювана тема карти, а не висновок з одного положення.",
                [{"factor": "element_distribution", "placement": element, "count": count, "total": len(signs)}], 0.76, 1,
            ))
        modality, count = modalities.most_common(1)[0]
        if count >= 3:
            facts.append(_evidence_fact(
                f"dominant_modality_{modality}", "Провідна модальність", "synthesis",
                f"У карті повторюється спосіб {MODALITY_LABELS[modality]}: {count} із {len(signs)} врахованих планет містяться у цій модальності.",
                [{"factor": "modality_distribution", "placement": modality, "count": count, "total": len(signs)}], 0.74, 1,
            ))
    return facts, summary


def _chart_ruler_fact(chart: dict[str, Any], house_mapping: dict[str, int]) -> list[dict[str, Any]]:
    if not chart.get("birth_time_known"):
        return []
    asc = _sign(chart.get("ascendant_sign"))
    ruler = RULERS.get(asc)
    data = chart.get("planets", {}).get(ruler, {})
    sign = _sign(data.get("sign")) if isinstance(data, dict) else None
    if not ruler or not sign:
        return []
    _, label = PLANET_DOMAINS[ruler]
    house = house_mapping.get(ruler)
    area = f", у сфері {HOUSE_AREAS[house]}" if house else ""
    statement = f"Управитель Асцендента — {label} у знаку {sign}{area}. Це зв’язує спосіб самопрезентації з темами цієї планети, знака та дому."
    return [_evidence_fact(
        "chart_ruler", "Управитель Асцендента", "synthesis", statement,
        [{"factor": "Ascendant ruler", "placement": f"{label} in {sign}", "house": house}], 0.82, 1,
    )]


def build_report_context(chart: dict[str, Any]) -> dict[str, Any]:
    """Return report_context_v2 with traceable natal evidence."""
    birth_time_known = bool(chart.get("birth_time_known", False))
    placements = [("Sun", _sign(chart.get("sun_sign"))), ("Moon", _sign(chart.get("moon_sign")))]
    if birth_time_known:
        placements.append(("Ascendant", _sign(chart.get("ascendant_sign"))))
    legacy = []
    for factor, placement in placements:
        for rule in RULES.get((factor, placement), []) if placement else []:
            legacy.append(_fact_from_rule(factor, placement, rule))
    legacy = sorted(legacy, key=lambda f: (f["writer_guidance"]["priority"], -f["confidence"]))[:12]
    house_facts, house_mapping = _house_facts(chart)
    distribution_facts, distribution = _distribution_facts(chart)
    facts = legacy + _planet_placement_facts(chart) + house_facts + _aspect_facts(chart) + distribution_facts + _chart_ruler_fact(chart, house_mapping)
    facts = [fact for fact in facts if fact["confidence"] >= 0.55]
    facts.sort(key=lambda f: (f["writer_guidance"]["priority"], -f["confidence"], f["id"]))
    facts = facts[:40]
    return {
        "schema_version": "2.0.0", "kb_version": "2.0.0", "prompt_version": "2.0.0",
        "report": {"report_id": str(chart.get("report_id") or f"rep_{uuid4().hex[:12]}"), "language": "uk", "report_type": "personality", "created_at": datetime.now(timezone.utc).isoformat()},
        "person": {"name": chart.get("name"), "birth_date": chart.get("birth_date"), "birth_time": chart.get("birth_time"), "birth_place": chart.get("birth_place") or chart.get("birthplace")},
        "chart_summary": {"sun_sign": _sign(chart.get("sun_sign")), "moon_sign": _sign(chart.get("moon_sign")), "ascendant_sign": _sign(chart.get("ascendant_sign")) if birth_time_known else None, "birth_time_known": birth_time_known, **distribution},
        "facts": facts,
    }