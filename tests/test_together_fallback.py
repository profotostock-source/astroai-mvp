from services.together_fallback import build_together_fallback


def test_fallback_has_nine_substantial_ukrainian_sections():
    context = {
        "person_a": {"name": "Микола"},
        "person_b": {"name": "Євгенія"},
        "strongest_aspects": [
            {"planet_a": "sun", "planet_b": "moon", "aspect": "trine", "orb": 2.4}
        ],
    }
    text = build_together_fallback(context, {}, {})

    assert all(f"Секція {number:02d}." in text for number in range(1, 10))
    assert "Сонце" in text and "Місяць" in text and "тригон" in text
    assert len(text.split()) >= 850
    assert "Ie shchos" not in text
    assert "Razom vy" not in text
