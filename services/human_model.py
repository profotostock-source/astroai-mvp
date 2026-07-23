"""Build a compact, traceable symbolic human model from natal-chart factors.

The scores are not psychological measurements. They are deterministic summaries of
astrological symbols used only to organize the report-writing context.
"""

from __future__ import annotations

from typing import Any

from services.interpretation_engine import ELEMENTS, MODALITIES, RULERS, _normalise_sign, _planet_info


SIGN_DIMENSIONS: dict[str, dict[str, int]] = {
    "Aries": {"autonomy": 25, "initiative": 30, "directness": 25, "stability": -10},
    "Taurus": {"stability": 30, "persistence": 25, "practicality": 25, "adaptability": -15},
    "Gemini": {"curiosity": 30, "adaptability": 25, "communication": 25, "stability": -10},
    "Cancer": {"emotional_security": 30, "care": 25, "belonging": 25, "directness": -10},
    "Leo": {"self_expression": 30, "confidence": 20, "recognition": 25, "adaptability": -5},
    "Virgo": {"practicality": 25, "discernment": 30, "structure": 20, "spontaneity": -10},
    "Libra": {"diplomacy": 30, "cooperation": 25, "balance": 25, "directness": -15},
    "Scorpio": {"depth": 30, "persistence": 20, "privacy": 25, "lightness": -10},
    "Sagittarius": {"freedom": 30, "meaning": 25, "exploration": 25, "stability": -10},
    "Capricorn": {"structure": 30, "responsibility": 30, "persistence": 20, "spontaneity": -15},
    "Aquarius": {"independent_thinking": 30, "innovation": 30, "freedom": 20, "conformity": -20},
    "Pisces": {"sensitivity": 30, "imagination": 30, "receptivity": 20, "structure": -10},
}

ELEMENT_DIMENSIONS = {
    "fire": {"initiative": 8, "self_expression": 7, "spontaneity": 6},
    "earth": {"stability": 8, "practicality": 8, "structure": 6},
    "air": {"communication": 8, "curiosity": 7, "independent_thinking": 5},
    "water": {"sensitivity": 8, "emotional_security": 7, "receptivity": 6},
}

MODALITY_DIMENSIONS = {
    "cardinal": {"initiative": 7, "directness": 4},
    "fixed": {"persistence": 8, "stability": 5, "adaptability": -4},
    "mutable": {"adaptability": 8, "receptivity": 5, "structure": -3},
}

FACTOR_WEIGHTS = {
    "sun": 1.00,
    "moon": 0.85,
    "ascendant": 0.90,
    "ascendant_ruler": 0.70,
    "mercury": 0.45,
    "venus": 0.40,
    "mars": 0.45,
    "saturn": 0.30,
    "uranus": 0.25,
}

DISPLAY_NAMES = {
    "autonomy": "потреба в автономії",
    "initiative": "ініціативність",
    "directness": "прямота",
    "stability": "потреба у стабільності",
    "persistence": "послідовність",
    "practicality": "практичність",
    "adaptability": "гнучкість",
    "curiosity": "допитливість",
    "communication": "потреба в обміні думками",
    "emotional_security": "потреба в емоційній безпеці",
    "care": "турботливість",
    "belonging": "потреба у відчутті належності",
    "self_expression": "самовираження",
    "confidence": "впевненість у прояві себе",
    "recognition": "потреба у визнанні",
    "discernment": "аналітичність",
    "structure": "потреба у структурі",
    "spontaneity": "спонтанність",
    "diplomacy": "дипломатичність",
    "cooperation": "схильність до співпраці",
    "balance": "пошук балансу",
    "depth": "потреба в глибині",
    "privacy": "потреба у приватності",
    "meaning": "пошук сенсу",
    "exploration": "потреба у розширенні досвіду",
    "freedom": "потреба у свободі",
    "responsibility": "відповідальність",
    "independent_thinking": "незалежність мислення",
    "innovation": "орієнтація на нове",
    "conformity": "схильність пристосовуватися до норм",
    "sensitivity": "чутливість",
    "imagination": "образність мислення",
    "receptivity": "сприйнятливість",
    "lightness": "потреба у легкості",
}


def _add_factor(scores: dict[str, float], evidence: dict[str, list[str]], sign: str | None, factor: str, label: str) -> None:
    if not sign or sign not in SIGN_DIMENSIONS:
        return
    weight = FACTOR_WEIGHTS[factor]
    payload = dict(SIGN_DIMENSIONS[sign])
    for key, value in ELEMENT_DIMENSIONS[ELEMENTS[sign]].items():
        payload[key] = payload.get(key, 0) + value
    for key, value in MODALITY_DIMENSIONS[MODALITIES[sign]].items():
        payload[key] = payload.get(key, 0) + value
    for dimension, contribution in payload.items():
        scores[dimension] = scores.get(dimension, 50.0) + contribution * weight
        evidence.setdefault(dimension, []).append(f"{label} у знаку {sign}")


def _bounded(value: float) -> int:
    return max(0, min(100, round(value)))


def build_human_model(chart: dict[str, Any]) -> dict[str, Any]:
    """Return Human Model v1 with scores, strongest themes and core tensions."""
    scores: dict[str, float] = {}
    evidence: dict[str, list[str]] = {}

    _add_factor(scores, evidence, _normalise_sign(chart.get("sun_sign")), "sun", "Сонце")
    _add_factor(scores, evidence, _normalise_sign(chart.get("moon_sign")), "moon", "Місяць")

    if chart.get("birth_time_known"):
        asc = _normalise_sign(chart.get("ascendant_sign"))
        _add_factor(scores, evidence, asc, "ascendant", "Асцендент")
        ruler = RULERS.get(asc or "")
        if ruler:
            _add_factor(
                scores,
                evidence,
                _normalise_sign(_planet_info(chart, ruler).get("sign")),
                "ascendant_ruler",
                f"Управитель Асцендента ({ruler.title()})",
            )

    for planet in ("mercury", "venus", "mars", "saturn", "uranus"):
        info = _planet_info(chart, planet)
        _add_factor(scores, evidence, _normalise_sign(info.get("sign")), planet, planet.title())

    dimensions = [
        {
            "id": key,
            "label": DISPLAY_NAMES.get(key, key),
            "score": _bounded(value),
            "evidence": evidence.get(key, []),
        }
        for key, value in scores.items()
    ]
    dimensions.sort(key=lambda item: abs(item["score"] - 50), reverse=True)

    high = [item for item in dimensions if item["score"] >= 68][:8]
    low = [item for item in dimensions if item["score"] <= 35][:5]

    tension_pairs = [
        ("freedom", "stability"),
        ("autonomy", "cooperation"),
        ("directness", "diplomacy"),
        ("spontaneity", "structure"),
        ("innovation", "stability"),
        ("sensitivity", "directness"),
    ]
    by_id = {item["id"]: item for item in dimensions}
    tensions = []
    for left_id, right_id in tension_pairs:
        left, right = by_id.get(left_id), by_id.get(right_id)
        if left and right and left["score"] >= 62 and right["score"] >= 62:
            tensions.append({
                "side_a": left["label"],
                "side_b": right["label"],
                "strength": round((left["score"] + right["score"]) / 2),
                "evidence": list(dict.fromkeys(left["evidence"] + right["evidence"])),
            })

    return {
        "model_version": "1.0",
        "method_note": "Symbolic astrological profile for report organization; not a psychological test.",
        "dimensions": dimensions,
        "strongest_dimensions": high,
        "lower_emphasis_dimensions": low,
        "core_tensions": tensions[:4],
        "writing_rules": {
            "scores_are_relative_not_diagnostic": True,
            "do_not_show_numeric_scores_to_reader": True,
            "every_claim_requires_evidence": True,
        },
    }
