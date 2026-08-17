"""Natal chart calculation service using Kerykeion.

This module provides astrology calculations for natal charts,
including zodiac signs, planet positions, houses, and aspects.
"""

import logging
import os
import re
from datetime import datetime

from database import get_cached_city, save_city_to_cache
from kerykeion import AstrologicalSubject


LOGGER = logging.getLogger(__name__)

# Alias map for common Ukrainian city name variants and transliterations
UKRAINIAN_CITY_ALIASES = {
    # Cyrillic spellings -> Latin transliterations
    "Одеса": "Odesa",
    "Одесса": "Odesa",  # Russian spelling
    "Київ": "Kyiv",
    "Киев": "Kyiv",  # Russian spelling
    "Львів": "Lviv",
    "Львов": "Lviv",  # Russian spelling
    "Харків": "Kharkiv",
    "Харьков": "Kharkiv",  # Russian spelling
    "Дніпро": "Dnipro",
    "Днепр": "Dnipro",  # Russian spelling
    "Донецьк": "Donetsk",
    "Донецк": "Donetsk",  # Russian spelling
    "Луганськ": "Luhansk",
    "Луганск": "Luhansk",  # Russian spelling
    "Запоріжжя": "Zaporizhzhia",
    "Запорожье": "Zaporizhzhia",  # Russian spelling
    "Вінниця": "Vinnytsia",
    "Винница": "Vinnytsia",  # Russian spelling
    "Чернівці": "Chernivtsi",
    "Черновцы": "Chernivtsi",  # Russian spelling
    "Полтава": "Poltava",
    "Суми": "Sumy",
    "Сумы": "Sumy",  # Russian spelling
    "Чернігів": "Chernihiv",
    "Чернигов": "Chernihiv",  # Russian spelling
    "Хмельницький": "Khmelnytskyi",
    "Хмельницкий": "Khmelnytskyi",  # Russian spelling
    "Тернопіль": "Ternopil",
    "Тернополь": "Ternopil",  # Russian spelling
    "Кропивницький": "Kropyvnytskyi",
    "Кировоград": "Kropyvnytskyi",  # Old Russian name
    "Вінниця": "Vinnytsia",
    # Common Latin-alphabet spelling variants
    "Odessa": "Odesa",   # Traditional double-s English spelling
    "Kiev": "Kyiv",      # Old English spelling
}

# Case-folded lookup: casefolded key -> canonical value
# Covers both Cyrillic variants and English transliterations (e.g. "odesa" -> "Odesa")
_CITY_ALIASES_CASEFOLDED: dict[str, str] = {
    **{k.casefold(): v for k, v in UKRAINIAN_CITY_ALIASES.items()},
    **{v.casefold(): v for v in UKRAINIAN_CITY_ALIASES.values()},
}

# Casefolded set of canonical city names for fast retry detection
_UKRAINIAN_CANONICAL_CASEFOLDED: frozenset[str] = frozenset(
    v.casefold() for v in UKRAINIAN_CITY_ALIASES.values()
)


# Latin characters that are visually identical to Cyrillic ones. A mixed
# keyboard layout produces words like "Украiна" (Latin "i") that never match a
# Cyrillic alias, so we repair them before lookup.
_LATIN_TO_CYRILLIC = str.maketrans({
    "a": "а", "c": "с", "e": "е", "i": "і", "o": "о", "p": "р", "x": "х", "y": "у",
    "s": "ѕ", "j": "ј",
})

_CYRILLIC_RE = re.compile(r"[Ѐ-ӿ]")


def _fold(text: str) -> str:
    """Casefold and repair Latin/Cyrillic homoglyphs for alias matching.

    Homoglyph repair only applies to strings that already contain Cyrillic, so
    genuinely Latin input like "Ukraine" is left untouched.
    """
    folded = " ".join(text.strip().casefold().split())
    if _CYRILLIC_RE.search(folded):
        folded = folded.translate(_LATIN_TO_CYRILLIC)
    return folded.replace("'", "").replace("’", "").replace("`", "")


# Accepted spellings of Ukraine, including frequent typos. Anything starting
# with "укра"/"ukra" is also treated as Ukraine (see normalize_birthplace).
_UKRAINE_ALIASES: frozenset[str] = frozenset({
    "україна", "украіна", "украина", "украйна", "вкраїна", "укр", "укр.",
    "ukraine", "ukraina", "ukrayina", "ukr", "ua",
})


class AstrologyError(Exception):
    """Raised when astrology calculation fails."""

    pass


def normalize_birthplace(value: str) -> tuple[str, str | None]:
    """Normalize birthplace input to extract city and country.

    Handles various input formats:
    - "Одеса" -> ("Odesa", None)
    - "Одеса, Україна" -> ("Odesa", "Ukraine")
    - "Odesa" -> ("Odesa", None)
    - "Odesa, Ukraine" -> ("Odesa", "Ukraine")

    Args:
        value: User-provided birthplace string (can include city and country).

    Returns:
        tuple[str, str | None]: Tuple of (normalized_city, country_code_or_name).
            country is None if not provided.
            city is normalized using alias map if available.

    Example:
        >>> normalize_birthplace("Одеса, Україна")
        ("Odesa", "Ukraine")
        >>> normalize_birthplace("Kyiv")
        ("Kyiv", None)
    """
    # Trim whitespace and normalize multiple spaces
    normalized = " ".join(value.strip().split())

    # Split by comma if present
    parts = [part.strip() for part in normalized.split(",")]

    city = parts[0]
    country = parts[1] if len(parts) > 1 else None

    # Apply alias map to normalize city name (case-insensitive, homoglyph-tolerant)
    canonical = _CITY_ALIASES_CASEFOLDED.get(_fold(city))
    if canonical is not None:
        city = canonical

    # Normalize country names
    if country:
        country_key = _fold(country)
        if (
            country_key in _UKRAINE_ALIASES
            or country_key.startswith("укра")
            or country_key.startswith("ukra")
        ):
            country = "UA"
        # Keep other country names as-is (GeoNames accepts various formats)

    return city, country


def _make_cache_keys(city: str, country: str | None) -> tuple[str, str]:
    """Generate normalized SQLite cache keys from a canonical city and country.

    Args:
        city: Canonical city name (already alias-resolved by normalize_birthplace).
        country: Country code string, or None.

    Returns:
        tuple[str, str]: (city_key, country_key) both casefolded for consistent lookup.
    """
    return city.casefold(), (country or "").casefold()


def _parse_birth_date(birth_date: str) -> tuple[int, int, int]:
    """Parse birth date from DD.MM.YYYY format.

    Args:
        birth_date: Birth date string in DD.MM.YYYY format.

    Returns:
        tuple[int, int, int]: Tuple of (day, month, year).

    Raises:
        AstrologyError: If date format is invalid.
    """
    try:
        parsed = datetime.strptime(birth_date, "%d.%m.%Y")
        return parsed.day, parsed.month, parsed.year
    except ValueError as error:
        msg = f"Invalid birth date format: {birth_date}. Expected DD.MM.YYYY"
        LOGGER.error(msg)
        raise AstrologyError(msg) from error


def _parse_birth_time(birth_time: str) -> tuple[int, int, bool]:
    """Parse birth time from HH:MM format.

    Args:
        birth_time: Birth time string in HH:MM format, or unknown phrase.

    Returns:
        tuple[int, int, bool]: Tuple of (hour, minute, is_known).
            If unknown, returns (12, 0, False).

    Raises:
        AstrologyError: If time format is invalid.
    """
    unknown_phrases = (
        "не знаю",
        "невідомо",
        "не пам'ятаю",
        "не пам'ятаю",
        "unknown",
    )
    
    if birth_time.lower() in unknown_phrases:
        LOGGER.info("Birth time marked as unknown: %s", birth_time)
        return 12, 0, False

    try:
        parsed = datetime.strptime(birth_time, "%H:%M")
        return parsed.hour, parsed.minute, True
    except ValueError as error:
        msg = f"Invalid birth time format: {birth_time}. Expected HH:MM"
        LOGGER.error(msg)
        raise AstrologyError(msg) from error


def _extract_planets_data(subject: AstrologicalSubject) -> dict:
    """Extract planet positions and signs from AstrologicalSubject.

    Args:
        subject: Kerykeion AstrologicalSubject instance.

    Returns:
        dict: Dictionary with planet data including sign and degree.
    """
    planets_data = {}
    model = subject.model()

    planet_names = [
        "sun",
        "moon",
        "mercury",
        "venus",
        "mars",
        "jupiter",
        "saturn",
        "uranus",
        "neptune",
        "pluto",
    ]

    for planet_name in planet_names:
        if hasattr(model, planet_name):
            planet = getattr(model, planet_name)
            planets_data[planet_name] = {
                "sign": planet.sign if hasattr(planet, "sign") else "N/A",
                "degree": planet.position if hasattr(planet, "position") else 0,
                "retrograde": planet.retrograde if hasattr(planet, "retrograde") else False,
            }

    return planets_data


def _extract_houses_data(subject: AstrologicalSubject) -> list[dict]:
    """Extract house information from AstrologicalSubject.

    Args:
        subject: Kerykeion AstrologicalSubject instance.

    Returns:
        list[dict]: List of 12 house dictionaries with cusps and signs.
    """
    houses_list = []
    model = subject.model()

    house_names = [
        "first_house",
        "second_house",
        "third_house",
        "fourth_house",
        "fifth_house",
        "sixth_house",
        "seventh_house",
        "eighth_house",
        "ninth_house",
        "tenth_house",
        "eleventh_house",
        "twelfth_house",
    ]

    for idx, house_name in enumerate(house_names, start=1):
        if hasattr(model, house_name):
            house = getattr(model, house_name)
            houses_list.append({
                "house": idx,
                "sign": house.sign if hasattr(house, "sign") else "N/A",
                "degree": house.position if hasattr(house, "position") else 0,
            })

    return houses_list


def _extract_aspects_data(subject: AstrologicalSubject) -> tuple[list[dict], list[str]]:
    """Extract natal aspects through the Kerykeion v5 chart-data API."""
    try:
        from kerykeion import ChartDataFactory

        chart_data = ChartDataFactory.create_natal_chart_data(subject.model())
        aspects = []
        for item in chart_data.aspects:
            aspects.append({
                "planet1": item.p1_name,
                "planet2": item.p2_name,
                "aspect": item.aspect,
                "orb": item.orbit,
                "movement": item.aspect_movement,
            })
        if not aspects:
            return [], ["No natal aspects were returned for the active points."]
        return aspects, []
    except Exception as error:
        LOGGER.warning("Failed to extract aspects through ChartDataFactory: %s", error)
        return [], [f"Aspect calculation failed: {error}"]


def calculate_natal_chart(profile: dict) -> dict:
    """Calculate natal chart for a user profile.

    Uses Kerykeion with Swiss Ephemeris to compute planetary positions,
    zodiac signs, houses, and aspects based on birth data.

    Args:
        profile: Dictionary containing user birth data:
            - name (str): User's name
            - birth_date (str): Birth date in DD.MM.YYYY format
            - birth_time (str): Birth time in HH:MM format or unknown phrase
            - birthplace (str): City and country of birth

    Returns:
        dict: Natal chart data including:
            - name: User's name
            - birth_date: Birth date
            - birth_time: Birth time (as provided)
            - birthplace: Birth place
            - birth_time_known: Boolean indicating if exact birth time was provided
            - sun_sign: Sun zodiac sign
            - moon_sign: Moon zodiac sign
            - ascendant_sign: Ascendant (rising sign) or None if time unknown
            - planets: Dictionary of planet positions with signs and degrees
            - houses: List of house cusps (empty if birth time unknown)
            - aspects: List of planetary aspects
            - warnings: List of any warnings or limitations

    Raises:
        AstrologyError: If birth data is invalid or birthplace cannot be resolved.

    Example:
        >>> profile = {
        ...     'name': 'John',
        ...     'birth_date': '15.03.1990',
        ...     'birth_time': '14:30',
        ...     'birthplace': 'London'
        ... }
        >>> chart = calculate_natal_chart(profile)
        >>> print(chart['sun_sign'])
        Pisces
    """
    warnings_list: list[str] = []

    geonames_username = os.getenv("KERYKEION_GEONAMES_USERNAME")
    if not geonames_username:
        msg = (
            "KERYKEION_GEONAMES_USERNAME is not set. "
            "Add it to your .env file. "
            "Register a free account at https://www.geonames.org/login"
        )
        LOGGER.error(msg)
        raise AstrologyError(msg)

    try:
        day, month, year = _parse_birth_date(profile["birth_date"])
        hour, minute, birth_time_known = _parse_birth_time(profile["birth_time"])

        LOGGER.info(
            "Calculating natal chart for %s born %d.%d.%d at %02d:%02d (time_known=%s)",
            profile["name"],
            day,
            month,
            year,
            hour,
            minute,
            birth_time_known,
        )

        # Normalize and parse birthplace
        city, country = normalize_birthplace(profile["birthplace"])
        LOGGER.info(
            "Normalized birthplace: city=%s, country=%s (from input: %s)",
            city,
            country,
            profile["birthplace"],
        )

        city_key, country_key = _make_cache_keys(city, country)

        # --- Cache check ---
        subject = None
        cached = None
        try:
            cached = get_cached_city(city_key, country_key)
        except Exception as cache_read_error:
            LOGGER.warning("City cache read failed (will use GeoNames): %s", cache_read_error)

        if cached is not None:
            LOGGER.info("City cache HIT: %s (country_key=%r)", city, country_key or "none")
            subject = AstrologicalSubject(
                name=profile["name"],
                year=year,
                month=month,
                day=day,
                hour=hour,
                minute=minute,
                lat=cached["latitude"],
                lng=cached["longitude"],
                tz_str=cached["timezone"],
                online=False,
            )
        else:
            LOGGER.info("City cache MISS: %s (country_key=%r)", city, country_key or "none")

            # --- GeoNames / Kerykeion geocoding ---
            first_attempt_error = None

            # First attempt: use city and country (if provided)
            try:
                if country:
                    subject = AstrologicalSubject(
                        name=profile["name"],
                        year=year,
                        month=month,
                        day=day,
                        hour=hour,
                        minute=minute,
                        city=city,
                        nation=country,
                        geonames_username=geonames_username,
                    )
                else:
                    subject = AstrologicalSubject(
                        name=profile["name"],
                        year=year,
                        month=month,
                        day=day,
                        hour=hour,
                        minute=minute,
                        city=city,
                        geonames_username=geonames_username,
                    )
                LOGGER.info("Geocoding successful on first attempt")
            except Exception as error:
                first_attempt_error = error
                LOGGER.debug("First geocoding attempt failed: %s", error)

                # Retry logic: if city is a known Ukrainian city and no country was provided,
                # retry with Ukraine as the country
                if country is None and city.casefold() in _UKRAINIAN_CANONICAL_CASEFOLDED:
                    LOGGER.info("City %s is a known Ukrainian city, retrying with UA", city)
                    try:
                        subject = AstrologicalSubject(
                            name=profile["name"],
                            year=year,
                            month=month,
                            day=day,
                            hour=hour,
                            minute=minute,
                            city=city,
                            nation="UA",
                            geonames_username=geonames_username,
                        )
                        LOGGER.info("Geocoding successful on retry with UA")
                    except Exception as retry_error:
                        LOGGER.debug("Retry with Ukraine failed: %s", retry_error)
                        # Keep the original error for reporting

                # A country the user misspelled ("Украіна", "Украна", ...) is
                # passed to GeoNames verbatim and poisons the whole lookup.
                # Retry with the city alone before giving up.
                elif country is not None:
                    LOGGER.info(
                        "Retrying geocoding for %s without the country %r", city, country
                    )
                    try:
                        subject = AstrologicalSubject(
                            name=profile["name"],
                            year=year,
                            month=month,
                            day=day,
                            hour=hour,
                            minute=minute,
                            city=city,
                            geonames_username=geonames_username,
                        )
                        LOGGER.info("Geocoding successful on retry without country")
                        # Do not cache under the unusable country string.
                        country = None
                        city_key, country_key = _make_cache_keys(city, country)
                    except Exception as retry_error:
                        LOGGER.debug("Retry without country failed: %s", retry_error)
                        # Keep the original error for reporting

            # If both attempts failed, raise error
            if subject is None:
                error_msg = (
                    "Не вдалося знайти місце народження. "
                    "Введіть місто та країну, наприклад: Одеса, Україна."
                )
                LOGGER.error(
                    "=== ORIGINAL EXCEPTION (before wrapping in AstrologyError) ===\n"
                    "Exception Type: %s\n"
                    "Exception Message: %s\n"
                    "Occurred at: AstrologicalSubject() instantiation\n"
                    "Location: calculate_natal_chart, after normalization\n"
                    "Birthplace input: %s\n"
                    "Normalized city: %s, country: %s\n"
                    "Full stack trace:",
                    type(first_attempt_error).__name__,
                    str(first_attempt_error),
                    profile["birthplace"],
                    city,
                    country,
                    exc_info=True
                )
                raise AstrologyError(error_msg) from first_attempt_error

            # --- Save successful geocoding result to cache ---
            try:
                resolved = subject.model()
                res_lat = getattr(resolved, "lat", None)
                res_lng = getattr(resolved, "lng", None)
                res_tz = getattr(resolved, "tz_str", None)
                res_nation = getattr(resolved, "nation", None) or (country or "")
                if res_lat is not None and res_lng is not None and res_tz:
                    save_city_to_cache(
                        city_key=city_key,
                        country_key=country_key,
                        city_name=city,
                        country_code=str(res_nation),
                        latitude=float(res_lat),
                        longitude=float(res_lng),
                        tz_str=str(res_tz),
                    )
                    LOGGER.info("City cached successfully: %s", city)
                else:
                    LOGGER.warning(
                        "Skipping cache: incomplete coords for %s (lat=%s lng=%s tz=%s)",
                        city, res_lat, res_lng, res_tz,
                    )
            except Exception as cache_write_error:
                LOGGER.warning("Failed to cache city %s: %s", city, cache_write_error)

        model = subject.model()

        sun_sign = model.sun.sign if hasattr(model.sun, "sign") else "N/A"
        moon_sign = model.moon.sign if hasattr(model.moon, "sign") else "N/A"

        if birth_time_known:
            ascendant_sign = (
                model.ascendant.sign if hasattr(model.ascendant, "sign") else "N/A"
            )
        else:
            ascendant_sign = None
            warnings_list.append(
                "Час народження невідомий. Розраховані позиції планет, але "
                "асцендент та дома потребують точного часу народження."
            )

        planets_data = _extract_planets_data(subject)
        
        if birth_time_known:
            houses_data = _extract_houses_data(subject)
        else:
            houses_data = []

        aspects_data, aspect_warnings = _extract_aspects_data(subject)
        warnings_list.extend(aspect_warnings)

        natal_chart = {
            "name": profile["name"],
            "birth_date": profile["birth_date"],
            "birth_time": profile["birth_time"],
            "birthplace": profile["birthplace"],
            "birth_time_known": birth_time_known,
            "sun_sign": sun_sign,
            "moon_sign": moon_sign,
            "ascendant_sign": ascendant_sign,
            "planets": planets_data,
            "houses": houses_data,
            "aspects": aspects_data,
            "warnings": warnings_list,
        }

        LOGGER.info(
            "Natal chart calculated successfully for %s: %s %s %s",
            profile["name"],
            sun_sign,
            moon_sign,
            ascendant_sign,
        )

        return natal_chart

    except AstrologyError:
        raise
    except Exception as error:
        msg = f"Failed to calculate natal chart: {error}"
        # Log the ORIGINAL exception details before wrapping
        LOGGER.error(
            "=== ORIGINAL EXCEPTION (before wrapping in AstrologyError) ===\n"
            "Exception Type: %s\n"
            "Exception Message: %s\n"
            "Occurred at: Unknown location in calculate_natal_chart\n"
            "Full stack trace:",
            type(error).__name__,
            str(error),
            exc_info=True
        )
        LOGGER.exception(msg)
        raise AstrologyError(msg) from error


if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO,
    )

    print("=" * 70)
    print("TEST A: Valid city and known birth time")
    print("=" * 70)

    profile_a = {
        "name": "Alice",
        "birth_date": "15.03.1990",
        "birth_time": "14:30",
        "birthplace": "London",
    }

    print(f"Input: {profile_a}\n")

    try:
        chart_a = calculate_natal_chart(profile_a)
        print("✅ Chart calculated successfully!\n")
        print(f"Name: {chart_a['name']}")
        print(f"Birth Time Known: {chart_a['birth_time_known']}")
        print(f"Sun: {chart_a['sun_sign']}")
        print(f"Moon: {chart_a['moon_sign']}")
        print(f"Ascendant: {chart_a['ascendant_sign']}")
        print(f"Planets: {len(chart_a['planets'])} calculated")
        print(f"Houses: {len(chart_a['houses'])} calculated (should be 12)")
        print(f"Aspects: {len(chart_a['aspects'])} found")
        if chart_a["warnings"]:
            print(f"Warnings: {chart_a['warnings']}")
        else:
            print("No warnings")
    except AstrologyError as e:
        print(f"❌ AstrologyError: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

    print("\n" + "=" * 70)
    print("TEST B: Unknown birth time")
    print("=" * 70)

    profile_b = {
        "name": "Bob",
        "birth_date": "22.07.1985",
        "birth_time": "не знаю",
        "birthplace": "New York",
    }

    print(f"Input: {profile_b}\n")

    try:
        chart_b = calculate_natal_chart(profile_b)
        print("✅ Chart calculated successfully!\n")
        print(f"Name: {chart_b['name']}")
        print(f"Birth Time Known: {chart_b['birth_time_known']}")
        print(f"Sun: {chart_b['sun_sign']}")
        print(f"Moon: {chart_b['moon_sign']}")
        print(f"Ascendant: {chart_b['ascendant_sign']} (should be None)")
        print(f"Planets: {len(chart_b['planets'])} calculated")
        print(f"Houses: {len(chart_b['houses'])} (should be 0)")
        print(f"Aspects: {len(chart_b['aspects'])} found")
        if chart_b["warnings"]:
            print(f"\nWarnings:")
            for warning in chart_b["warnings"]:
                print(f"  ⚠️  {warning}")
    except AstrologyError as e:
        print(f"❌ AstrologyError: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

    print("\n" + "=" * 70)
    print("TEST C: Invalid city (should raise AstrologyError)")
    print("=" * 70)

    profile_c = {
        "name": "Charlie",
        "birth_date": "01.01.2000",
        "birth_time": "10:00",
        "birthplace": "NonExistentCityXYZ123",
    }

    print(f"Input: {profile_c}\n")

    try:
        chart_c = calculate_natal_chart(profile_c)
        print("❌ ERROR: Chart was calculated when it should have failed!")
        print(f"Chart: {chart_c}")
    except AstrologyError as e:
        print(f"✅ AstrologyError raised as expected:")
        print(f"   Message: {e}")
    except Exception as e:
        print(f"❌ Unexpected error type: {type(e).__name__}: {e}")
