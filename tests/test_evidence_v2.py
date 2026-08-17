"""Contract tests for the richer natal evidence context."""

from services.evidence_builder import build_report_context


def _chart(time_known=True):
    signs = ["Ari", "Tau", "Gem", "Can", "Leo", "Vir", "Lib", "Sco", "Sag", "Cap", "Aqu", "Pis"]
    return {
        "name": "Test",
        "birth_time_known": time_known,
        "sun_sign": "Ari",
        "moon_sign": "Can",
        "ascendant_sign": "Lib" if time_known else None,
        "planets": {
            "sun": {"sign": "Ari", "degree": 10.0, "retrograde": False},
            "moon": {"sign": "Can", "degree": 12.0, "retrograde": False},
            "mercury": {"sign": "Ari", "degree": 15.0, "retrograde": True},
            "venus": {"sign": "Tau", "degree": 8.0, "retrograde": False},
            "mars": {"sign": "Cap", "degree": 20.0, "retrograde": False},
            "jupiter": {"sign": "Sag", "degree": 5.0, "retrograde": False},
            "saturn": {"sign": "Cap", "degree": 4.0, "retrograde": False},
        },
        "houses": [{"house": i + 1, "sign": sign, "degree": 0.0} for i, sign in enumerate(signs)] if time_known else [],
        "aspects": [
            {"planet1": "Sun", "planet2": "Moon", "aspect": "square", "orb": 2.0},
            {"planet1": "Venus", "planet2": "Mars", "aspect": "trine", "orb": 1.5},
        ],
        "warnings": [],
    }


def test_v2_contains_multiple_evidence_layers():
    context = build_report_context(_chart())
    categories = {fact["category"] for fact in context["facts"]}
    assert context["schema_version"] == "2.0.0"
    assert {"placement", "house", "aspect", "synthesis"} <= categories
    assert len(context["facts"]) > 12


def test_v2_preserves_orb_and_retrograde_evidence():
    context = build_report_context(_chart())
    aspects = [fact for fact in context["facts"] if fact["category"] == "aspect"]
    mercury = next(fact for fact in context["facts"] if fact["id"].startswith("planet_mercury_"))
    assert any(fact["evidence"][0]["orb"] == 1.5 for fact in aspects)
    assert mercury["evidence"][0]["retrograde"] is True


def test_unknown_time_excludes_houses_and_chart_ruler():
    context = build_report_context(_chart(time_known=False))
    ids = {fact["id"] for fact in context["facts"]}
    assert not any(fact["category"] == "house" for fact in context["facts"])
    assert "chart_ruler" not in ids
    assert context["chart_summary"]["ascendant_sign"] is None