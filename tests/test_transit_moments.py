"""Ensure every Year transit card contains actionable detail."""

from knowledge.transit_rules import get_moment_desc


def test_unmapped_transits_get_concrete_fallback():
    cases = [
        ("Pluto", "trine", "venus"),
        ("Saturn", "conjunction", "ascendant"),
        ("Saturn", "sextile", "venus"),
    ]
    for planet, aspect, point in cases:
        title, description = get_moment_desc(planet, aspect, point)
        assert title
        assert "Активний транзит" not in description
        assert "Ризик:" in description
        assert "Дія:" in description
        assert len(description) > 300


def test_known_custom_transit_keeps_curated_copy():
    title, description = get_moment_desc("Pluto", "square", "ascendant")
    assert "позицію" in title
    assert "пряма розмова" in description.lower()