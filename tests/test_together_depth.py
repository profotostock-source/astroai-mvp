import re

from services.together_fallback import build_together_fallback


def test_each_together_section_has_substantial_depth_and_evidence():
    context = {
        "person_a": {"name": "Микола"},
        "person_b": {"name": "Євгенія"},
        "strongest_aspects": [
            {"planet_a": "sun", "planet_b": "moon", "aspect": "trine", "orb": 2.4, "score": 4.2}
        ],
        "themes": {
            key: [{"planet_a": "sun", "planet_b": "moon", "aspect": "trine", "orb": 2.4, "score": 4.2}]
            for key in ("attraction", "emotional", "love_style", "communication", "conflict", "stability", "growth")
        },
    }
    text = build_together_fallback(context, {}, {})
    parts = re.split(r"Секція\s+(\d{2})\.[^\n]*\n", text)
    sections = {int(parts[i]): parts[i + 1] for i in range(1, len(parts) - 1, 2)}

    assert len(sections) == 9
    assert all(len(body.split()) >= 160 for body in sections.values())
    assert all("орбіс" in body for body in sections.values())
