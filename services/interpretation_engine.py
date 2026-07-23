"""Rule-based preparation of natal-chart evidence for AI writing.

The engine owns selection, weighting and synthesis of chart factors. The language
model receives a constrained, traceable context and is used as a writer, not as
the primary chart analyst.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


SIGN_ALIASES = {
    "Ari": "Aries", "Tau": "Taurus", "Gem": "Gemini", "Can": "Cancer",
    "Leo": "Leo", "Vir": "Virgo", "Lib": "Libra", "Sco": "Scorpio",
    "Sag": "Sagittarius", "Cap": "Capricorn", "Aqu": "Aquarius", "Pis": "Pisces",
}

SIGN_THEMES: dict[str, tuple[str, ...]] = {
    "Aries": ("initiative", "independence", "direct action"),
    "Taurus": ("stability", "consistency", "practicality"),
    "Gemini": ("curiosity", "adaptability", "exchange of ideas"),
    "Cancer": ("emotional safety", "care", "belonging"),
    "Leo": ("self-expression", "visibility", "creative confidence"),
    "Virgo": ("discernment", "usefulness", "attention to detail"),
    "Libra": ("balance", "diplomacy", "consideration of others"),
    "Scorpio": ("depth", "intensity", "inner transformation"),
    "Sagittarius": ("meaning", "freedom", "broad perspective"),
    "Capricorn": ("responsibility", "structure", "long-term results"),
    "Aquarius": ("independent thinking", "innovation", "freedom of perspective"),
    "Pisces": ("sensitivity", "imagination", "receptivity"),
}

ELEMENTS = {
    "Aries": "fire", "Leo": "fire", "Sagittarius": "fire",
    "Taurus": "earth", "Virgo": "earth", "Capricorn": "earth",
    "Gemini": "air", "Libra": "air", "Aquarius": "air",
    "Cancer": "water", "Scorpio": "water", "Pisces": "water",
}

MODALITIES = {
    "Aries": "cardinal", "Cancer": "cardinal", "Libra": "cardinal", "Capricorn": "cardinal",
    "Taurus": "fixed", "Leo": "fixed", "Scorpio": "fixed", "Aquarius": "fixed",
    "Gemini": "mutable", "Virgo": "mutable", "Sagittarius": "mutable", "Pisces": "mutable",
}

RULERS = {
    "Aries": "mars", "Taurus": "venus", "Gemini": "mercury", "Cancer": "moon",
    "Leo": "sun", "Virgo": "mercury", "Libra": "venus", "Scorpio": "pluto",
    "Sagittarius": "jupiter", "Capricorn": "saturn", "Aquarius": "uranus", "Pisces": "neptune",
}

HARD_ASPECTS = {"square", "opposition", "conjunction"}
SOFT_ASPECTS = {"trine", "sextile"}


@dataclass(frozen=True)
class Factor:
    factor_id: str
    kind: str
    label: str
    sign: str | None
    weight: int
    themes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.factor_id,
            "kind": self.kind,
            "label": self.label,
            "sign": self.sign,
            "weight": self.weight,
            "themes": list(self.themes),
        }


def _normalise_sign(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    return SIGN_ALIASES.get(value, value if value in SIGN_THEMES else None)


def _planet_info(chart: dict, planet: str) -> dict:
    planets = chart.get("planets") or {}
    for key, value in planets.items():
        if str(key).casefold() == planet.casefold() and isinstance(value, dict):
            return value
    return {}


def _make_sign_factor(factor_id: str, kind: str, label: str, sign: Any, weight: int) -> Factor | None:
    normalized = _normalise_sign(sign)
    if not normalized:
        return None
    return Factor(factor_id, kind, label, normalized, weight, SIGN_THEMES[normalized])


def _find_aspects(chart: dict, body_name: str) -> list[dict[str, Any]]:
    result = []
    for raw in chart.get("aspects") or []:
        if not isinstance(raw, dict):
            continue
        p1 = str(raw.get("planet1", ""))
        p2 = str(raw.get("planet2", ""))
        if body_name.casefold() in {p1.casefold(), p2.casefold()}:
            result.append({
                "planet1": p1,
                "planet2": p2,
                "aspect": str(raw.get("aspect", "Unknown")),
                "orb": raw.get("orb", 0),
            })
    return result


def _confidence(weights: list[int]) -> float:
    if not weights:
        return 0.0
    # One primary factor can support a reportable theme; repetition raises confidence.
    score = max(weights) / 100 + max(0, len(weights) - 1) * 0.08
    return round(min(score, 0.98), 2)


def build_personality_core(chart: dict) -> dict[str, Any]:
    """Build a traceable analysis for the report's core-personality domain."""
    birth_time_known = bool(chart.get("birth_time_known", False))
    factors: list[Factor] = []

    candidates = [
        _make_sign_factor("sun_sign", "sun_sign", "Sun sign", chart.get("sun_sign"), 100),
        _make_sign_factor("moon_sign", "moon_sign", "Moon sign", chart.get("moon_sign"), 35),
    ]

    if birth_time_known:
        candidates.append(
            _make_sign_factor("ascendant_sign", "ascendant_sign", "Ascendant sign", chart.get("ascendant_sign"), 95)
        )
        asc_sign = _normalise_sign(chart.get("ascendant_sign"))
        ruler = RULERS.get(asc_sign or "")
        if ruler:
            ruler_info = _planet_info(chart, ruler)
            candidates.append(
                _make_sign_factor(
                    "ascendant_ruler_sign",
                    "ascendant_ruler",
                    f"Ascendant ruler {ruler.title()} sign",
                    ruler_info.get("sign"),
                    90,
                )
            )

    factors.extend(factor for factor in candidates if factor is not None)

    theme_support: dict[str, list[Factor]] = {}
    for factor in factors:
        for theme in factor.themes:
            theme_support.setdefault(theme, []).append(factor)

    patterns = []
    for theme, support in theme_support.items():
        weights = [factor.weight for factor in support]
        conf = _confidence(weights)
        if max(weights) >= 85 or len([w for w in weights if w >= 60]) >= 2 or len(weights) >= 3:
            patterns.append({
                "pattern": theme,
                "confidence": conf,
                "evidence_ids": [factor.factor_id for factor in support],
                "evidence": [factor.label + (f" in {factor.sign}" if factor.sign else "") for factor in support],
            })
    patterns.sort(key=lambda item: item["confidence"], reverse=True)

    # Create explicit tensions from differing elements/modalities among the major factors.
    major = [factor for factor in factors if factor.weight >= 85]
    tensions = []
    seen_pairs: set[tuple[str, str]] = set()
    for index, left in enumerate(major):
        for right in major[index + 1:]:
            if not left.sign or not right.sign:
                continue
            left_element, right_element = ELEMENTS[left.sign], ELEMENTS[right.sign]
            left_modality, right_modality = MODALITIES[left.sign], MODALITIES[right.sign]
            if left_element == right_element and left_modality == right_modality:
                continue
            key = tuple(sorted((left.factor_id, right.factor_id)))
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            tensions.append({
                "side_a": left.themes[0],
                "side_b": right.themes[0],
                "confidence": round(min((left.weight + right.weight) / 200, 0.95), 2),
                "evidence_ids": [left.factor_id, right.factor_id],
                "evidence": [f"{left.label} in {left.sign}", f"{right.label} in {right.sign}"],
                "possible_manifestation": (
                    f"A need for {left.themes[0]} may coexist with a need for {right.themes[0]}; "
                    "the writer must present this as a possibility, not a fact."
                ),
            })

    sun_aspects = _find_aspects(chart, "Sun")
    aspect_evidence = []
    for index, aspect in enumerate(sun_aspects):
        aspect_name = aspect["aspect"].casefold()
        tone = "integrating" if aspect_name in SOFT_ASPECTS else "dynamic" if aspect_name in HARD_ASPECTS else "neutral"
        aspect_evidence.append({"id": f"sun_aspect_{index + 1}", "tone": tone, **aspect})

    external_internal = None
    sun = next((f for f in factors if f.factor_id == "sun_sign"), None)
    asc = next((f for f in factors if f.factor_id == "ascendant_sign"), None)
    if sun and asc and sun.sign != asc.sign:
        external_internal = {
            "outer_style": asc.themes[0],
            "inner_direction": sun.themes[0],
            "confidence": 0.9,
            "evidence_ids": [asc.factor_id, sun.factor_id],
            "evidence": [f"Ascendant in {asc.sign}", f"Sun in {sun.sign}"],
        }

    return {
        "section": "personality_core",
        "engine_version": "1.0",
        "birth_time_known": birth_time_known,
        "factors": [factor.as_dict() for factor in factors],
        "dominant_patterns": patterns[:5],
        "tensions": tensions[:4],
        "external_internal_difference": external_internal,
        "sun_aspects": aspect_evidence,
        "writing_contract": {
            "must_cite_evidence_ids_internally": True,
            "do_not_print_evidence_ids": True,
            "minimum_confidence": 0.4,
            "prohibited_claims": [
                "diagnoses", "predictions", "categorical personality claims",
                "life events not present in input", "astrological facts absent from evidence",
            ],
        },
    }


def build_interpretation_context(chart: dict) -> dict[str, Any]:
    """Build the structured context passed to the language model."""
    human_model = __import__("services.human_model", fromlist=["build_human_model"]).build_human_model(chart)
    scenario_context = __import__("services.scenario_engine", fromlist=["build_scenario_context"]).build_scenario_context(
        chart, human_model
    )
    return {
        "context_version": "1.2",
        "person_name": chart.get("name"),
        "personality_core": build_personality_core(chart),
        "human_model": human_model,
        "scenario_context": scenario_context,
        # A factual catalog supports report sections not yet migrated to rule modules.
        # It contains no inferred life facts and remains fully traceable to the chart.
        "evidence_catalog": {
            "planets": chart.get("planets") or {},
            "houses": chart.get("houses") or [] if chart.get("birth_time_known") else [],
            "aspects": chart.get("aspects") or [],
            "warnings": chart.get("warnings") or [],
        },
    }
