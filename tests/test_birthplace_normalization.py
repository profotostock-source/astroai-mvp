from services.astrology import normalize_birthplace


def test_ukrainian_name_for_russia_becomes_iso_code():
    assert normalize_birthplace("Електросталь, Росія") == ("Електросталь", "RU")


def test_russian_name_for_russia_becomes_iso_code():
    assert normalize_birthplace("Электросталь, Россия") == ("Электросталь", "RU")
