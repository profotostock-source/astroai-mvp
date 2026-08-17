"""Tests for Inner Compass Together MVP.

Test couple:
  Person A: Anna, 15.03.1990, 10:00, Kyiv
  Person B: Maxim, 22.07.1988, 14:30, Lviv

Run with:
  cd /sessions/gallant-focused-archimedes/mnt/AstroAI_MVP
  python -m pytest tests/test_together.py -v
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Load .env manually (no load_dotenv() without path to avoid pitfalls)
env_file = ROOT / ".env"
if env_file.exists():
    with open(env_file, encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _k, _, _v = _line.partition("=")
                os.environ.setdefault(_k.strip(), _v.strip())


import pytest


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_chart_a():
    """Synthetic chart for Anna — known birth time."""
    return {
        "name": "Anna",
        "birth_date": "15.03.1990",
        "birth_time": "10:00",
        "birthplace": "Kyiv, UA",
        "birth_time_known": True,
        "sun_sign": "Pisces",
        "moon_sign": "Virgo",
        "ascendant_sign": "Cancer",
        "planets": {
            "sun":     {"sign": "Pis", "degree": 24.3, "retrograde": False},
            "moon":    {"sign": "Vir", "degree": 12.1, "retrograde": False},
            "mercury": {"sign": "Pis", "degree": 5.0,  "retrograde": False},
            "venus":   {"sign": "Aqu", "degree": 18.5, "retrograde": False},
            "mars":    {"sign": "Cap", "degree": 10.2, "retrograde": False},
            "jupiter": {"sign": "Can", "degree": 2.4,  "retrograde": False},
            "saturn":  {"sign": "Cap", "degree": 20.1, "retrograde": False},
            "uranus":  {"sign": "Cap", "degree": 4.8,  "retrograde": False},
            "neptune": {"sign": "Cap", "degree": 14.0, "retrograde": False},
            "pluto":   {"sign": "Sco", "degree": 16.3, "retrograde": False},
        },
        "houses": [
            {"house": 1, "sign": "Can", "degree": 5.2},
            {"house": 2, "sign": "Leo", "degree": 0.0},
        ],
        "aspects": [],
        "warnings": [],
    }


def _make_chart_b():
    """Synthetic chart for Maxim — known birth time."""
    return {
        "name": "Maxim",
        "birth_date": "22.07.1988",
        "birth_time": "14:30",
        "birthplace": "Lviv, UA",
        "birth_time_known": True,
        "sun_sign": "Cancer",
        "moon_sign": "Gemini",
        "ascendant_sign": "Scorpio",
        "planets": {
            "sun":     {"sign": "Can", "degree": 29.8, "retrograde": False},
            "moon":    {"sign": "Gem", "degree": 5.6,  "retrograde": False},
            "mercury": {"sign": "Leo", "degree": 8.2,  "retrograde": False},
            "venus":   {"sign": "Can", "degree": 15.3, "retrograde": False},
            "mars":    {"sign": "Ari", "degree": 22.0, "retrograde": False},
            "jupiter": {"sign": "Tau", "degree": 27.0, "retrograde": False},
            "saturn":  {"sign": "Sag", "degree": 27.4, "retrograde": False},
            "uranus":  {"sign": "Sag", "degree": 28.0, "retrograde": False},
            "neptune": {"sign": "Cap", "degree": 9.5,  "retrograde": False},
            "pluto":   {"sign": "Sco", "degree": 11.4, "retrograde": False},
        },
        "houses": [
            {"house": 1, "sign": "Sco", "degree": 12.0},
        ],
        "aspects": [],
        "warnings": [],
    }


def _make_profile_a():
    return {
        "name": "Anna",
        "birth_date": "15.03.1990",
        "birth_time": "10:00",
        "birthplace": "Kyiv, UA",
    }


def _make_profile_b():
    return {
        "name": "Maxim",
        "birth_date": "22.07.1988",
        "birth_time": "14:30",
        "birthplace": "Lviv, UA",
    }


# ── Test: synastry calculation ────────────────────────────────────────────────

def test_calculate_synastry_returns_list():
    from services.synastry import calculate_synastry
    chart_a = _make_chart_a()
    chart_b = _make_chart_b()
    aspects = calculate_synastry(chart_a, chart_b)
    assert isinstance(aspects, list), "calculate_synastry must return a list"
    assert len(aspects) > 0, "There should be at least some aspects between the test charts"


def test_synastry_aspect_schema():
    from services.synastry import calculate_synastry
    chart_a = _make_chart_a()
    chart_b = _make_chart_b()
    aspects = calculate_synastry(chart_a, chart_b)
    required_keys = {"planet_a", "planet_b", "aspect", "orb", "angle", "score", "direction"}
    for asp in aspects:
        missing = required_keys - set(asp.keys())
        assert not missing, f"Aspect missing keys: {missing}. Aspect: {asp}"


def test_synastry_sorted_by_score_descending():
    from services.synastry import calculate_synastry
    chart_a = _make_chart_a()
    chart_b = _make_chart_b()
    aspects = calculate_synastry(chart_a, chart_b)
    scores = [a["score"] for a in aspects]
    assert scores == sorted(scores, reverse=True), "Aspects must be sorted by score descending"


def test_synastry_orbs_within_bounds():
    from services.synastry import calculate_synastry
    from knowledge.synastry_orbs import SYNASTRY_ORBS
    chart_a = _make_chart_a()
    chart_b = _make_chart_b()
    aspects = calculate_synastry(chart_a, chart_b)
    for asp in aspects:
        max_orb = SYNASTRY_ORBS.get(asp["aspect"], 8)
        assert asp["orb"] <= max_orb, (
            f"Orb {asp['orb']} exceeds max {max_orb} for {asp['aspect']}"
        )


def test_synastry_unknown_birth_time_excludes_ascendant():
    from services.synastry import calculate_synastry
    chart_a = _make_chart_a()
    chart_b = _make_chart_b()
    chart_b["birth_time_known"] = False
    chart_b["ascendant_sign"] = None

    aspects = calculate_synastry(chart_a, chart_b)
    # No aspect should have planet_b == "ascendant"
    asc_b_aspects = [a for a in aspects if a["planet_b"] == "ascendant"]
    assert len(asc_b_aspects) == 0, (
        "Ascendant aspects for Person B should be excluded when birth time unknown"
    )


def test_get_planet_degree_returns_float():
    from services.synastry import get_planet_degree
    chart = _make_chart_a()
    deg = get_planet_degree("sun", chart)
    assert isinstance(deg, float), "get_planet_degree must return float"
    assert 0.0 <= deg < 360.0, f"Degree {deg} out of range [0, 360)"


def test_get_planet_degree_unknown_planet_returns_none():
    from services.synastry import get_planet_degree
    chart = _make_chart_a()
    result = get_planet_degree("nonexistent_planet", chart)
    assert result is None


# ── Test: evidence context ────────────────────────────────────────────────────

def test_build_together_context_schema():
    from services.synastry import calculate_synastry
    from services.together_evidence import build_together_context
    chart_a = _make_chart_a()
    chart_b = _make_chart_b()
    aspects = calculate_synastry(chart_a, chart_b)
    ctx = build_together_context(chart_a, chart_b, _make_profile_a(), _make_profile_b(), aspects)

    assert ctx["report_type"] == "together_v1"
    assert "person_a" in ctx
    assert "person_b" in ctx
    assert "strongest_aspects" in ctx
    assert "themes" in ctx
    assert "birth_time_known_a" in ctx
    assert "birth_time_known_b" in ctx


def test_build_together_context_theme_keys():
    from services.synastry import calculate_synastry
    from services.together_evidence import build_together_context, ALL_THEMES
    chart_a = _make_chart_a()
    chart_b = _make_chart_b()
    aspects = calculate_synastry(chart_a, chart_b)
    ctx = build_together_context(chart_a, chart_b, _make_profile_a(), _make_profile_b(), aspects)
    themes = ctx.get("themes", {})
    for theme in ALL_THEMES:
        assert theme in themes, f"Theme {theme} missing from context"


def test_build_together_context_names():
    from services.synastry import calculate_synastry
    from services.together_evidence import build_together_context
    chart_a = _make_chart_a()
    chart_b = _make_chart_b()
    aspects = calculate_synastry(chart_a, chart_b)
    ctx = build_together_context(chart_a, chart_b, _make_profile_a(), _make_profile_b(), aspects)
    assert ctx["person_a"]["name"] == "Anna"
    assert ctx["person_b"]["name"] == "Maxim"


def test_build_together_context_strongest_aspects_limit():
    from services.synastry import calculate_synastry
    from services.together_evidence import build_together_context
    chart_a = _make_chart_a()
    chart_b = _make_chart_b()
    aspects = calculate_synastry(chart_a, chart_b)
    ctx = build_together_context(chart_a, chart_b, _make_profile_a(), _make_profile_b(), aspects)
    assert len(ctx["strongest_aspects"]) <= 20


# ── Test: PDF generation ──────────────────────────────────────────────────────

def test_together_pdf_generates_without_error():
    """Generate a Together PDF for the test couple. No network needed."""
    from services.pdf_together_report import generate_together_report
    chart_a = _make_chart_a()
    chart_b = _make_chart_b()
    profile_a = _make_profile_a()
    profile_b = _make_profile_b()

    pdf_path = generate_together_report(
        profile_a=profile_a,
        profile_b=profile_b,
        telegram_user_id=99999,
        chart_a=chart_a,
        chart_b=chart_b,
    )
    assert pdf_path.exists(), f"PDF was not created at {pdf_path}"
    size = pdf_path.stat().st_size
    assert size > 10_000, f"PDF too small: {size} bytes — generation may have failed"


def test_together_pdf_saved_to_correct_path():
    """Verify the test PDF path and save a copy for manual inspection."""
    from services.pdf_together_report import generate_together_report
    chart_a = _make_chart_a()
    chart_b = _make_chart_b()

    pdf_path = generate_together_report(
        profile_a=_make_profile_a(),
        profile_b=_make_profile_b(),
        telegram_user_id=99999,
        chart_a=chart_a,
        chart_b=chart_b,
    )

    # Copy to together_test.pdf
    import shutil
    test_pdf = ROOT / "reports" / "together_test.pdf"
    shutil.copy(pdf_path, test_pdf)
    assert test_pdf.exists()


# ── Test: regression — existing products still work ──────────────────────────

def test_evidence_builder_regression():
    """Existing evidence_builder must still work with a minimal chart."""
    from services.evidence_builder import build_report_context
    chart = {
        "name": "Test",
        "birth_date": "01.01.1990",
        "birth_time": "12:00",
        "birthplace": "Kyiv",
        "birth_time_known": False,
        "sun_sign": "Capricorn",
        "moon_sign": "Scorpio",
        "ascendant_sign": None,
        "planets": {},
        "houses": [],
        "aspects": [],
        "warnings": [],
    }
    ctx = build_report_context(chart)
    assert ctx["report"]["report_type"] == "personality"
    assert "facts" in ctx


def test_synastry_score_is_positive():
    from services.synastry import calculate_synastry
    chart_a = _make_chart_a()
    chart_b = _make_chart_b()
    aspects = calculate_synastry(chart_a, chart_b)
    for asp in aspects:
        assert asp["score"] >= 0, f"Score must be non-negative: {asp}"


def test_database_together_functions():
    """DB save and retrieve Together report."""
    import database
    database.init_db()

    row_id = database.save_together_report(
        owner_user_id=99998,
        person_a_name="TestA",
        person_a_birth_date="01.01.1990",
        person_a_birth_time="10:00",
        person_a_birthplace="Kyiv",
        person_a_birth_time_known=True,
        person_b_name="TestB",
        person_b_birth_date="01.06.1985",
        person_b_birth_time="12:00",
        person_b_birthplace="Lviv",
        person_b_birth_time_known=True,
        report_path="/tmp/test.pdf",
    )
    assert row_id is not None and row_id > 0

    reports = database.get_together_reports(99998)
    assert len(reports) >= 1
    assert reports[0]["person_a_name"] == "TestA"
    assert reports[0]["person_b_name"] == "TestB"
