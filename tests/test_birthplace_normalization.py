from babel import Locale

from services.astrology import normalize_birthplace


def test_ukrainian_name_for_russia_becomes_iso_code():
    assert normalize_birthplace("Електросталь, Росія") == ("Електросталь", "RU")


def test_russian_name_for_russia_becomes_iso_code():
    assert normalize_birthplace("Электросталь, Россия") == ("Электросталь", "RU")


def test_every_cldr_country_name_in_supported_languages_becomes_iso_code():
    checked = 0
    for locale_name in ("uk", "ru", "en"):
        for code, country_name in Locale.parse(locale_name).territories.items():
            if len(code) != 2:
                continue
            _, normalized_country = normalize_birthplace(f"Test City, {country_name}")
            assert normalized_country == code.upper(), (locale_name, country_name, code)
            checked += 1
    assert checked >= 700


def test_iso_country_codes_are_case_insensitive():
    assert normalize_birthplace("Paris, fr") == ("Paris", "FR")
    assert normalize_birthplace("Tokyo, JP") == ("Tokyo", "JP")
