#!/usr/bin/env python3
"""Test suite for birthplace normalization and astrology calculations."""

import logging
import sys

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(levelname)s] %(name)s: %(message)s'
)

print("=" * 80)
print("TEST SUITE: Birthplace Normalization and Astrology Calculations")
print("=" * 80)

from services.astrology import normalize_birthplace, calculate_natal_chart, AstrologyError

# ============================================================================
# PART 1: Test normalize_birthplace() function
# ============================================================================

print("\n" + "=" * 80)
print("PART 1: Testing normalize_birthplace() helper function")
print("=" * 80)

test_cases_normalize = [
    # (input, expected_city, expected_country, description)
    ("Одеса", "Odesa", None, "Ukrainian city in Cyrillic"),
    ("Одеса, Україна", "Odesa", "Ukraine", "Ukrainian city with Ukraine"),
    ("Odesa", "Odesa", None, "English transliteration"),
    ("Odesa, Ukraine", "Odesa", "Ukraine", "English with country"),
    ("Київ", "Kyiv", None, "Kyiv in Cyrillic"),
    ("Киев", "Kyiv", None, "Kyiv in Russian spelling"),
    ("Киев, Україна", "Kyiv", "Ukraine", "Kyiv Russian + Ukraine"),
    ("  Одеса  ,  Україна  ", "Odesa", "Ukraine", "Extra whitespace"),
    ("Львів", "Lviv", None, "Lviv in Cyrillic"),
    ("Харків", "Kharkiv", None, "Kharkiv in Cyrillic"),
    ("Дніпро", "Dnipro", None, "Dnipro in Cyrillic"),
    ("London, United Kingdom", "London", "United Kingdom", "English city with country"),
    ("Paris", "Paris", None, "Non-Ukrainian city"),
    # Case-insensitive fixes (new tests)
    ("odesa", "Odesa", None, "odesa (all lowercase English)"),
    ("ODESA", "Odesa", None, "ODESA (all uppercase English)"),
    ("одеса", "Odesa", None, "одеса (lowercase Ukrainian Cyrillic)"),
    ("ОДЕСА", "Odesa", None, "ОДЕСА (uppercase Ukrainian Cyrillic)"),
    ("одесса", "Odesa", None, "одесса (lowercase Russian Cyrillic)"),
    ("Одесса", "Odesa", None, "Одесса (title-case Russian Cyrillic)"),
    ("Odesa, Ukraine", "Odesa", "Ukraine", "Odesa with Ukraine (English)"),
]

normalize_passed = 0
normalize_failed = 0

for input_val, expected_city, expected_country, description in test_cases_normalize:
    try:
        city, country = normalize_birthplace(input_val)
        if city == expected_city and country == expected_country:
            print(f"✓ PASS: {description}")
            print(f"  Input: '{input_val}' → City: '{city}', Country: {country}")
            normalize_passed += 1
        else:
            print(f"✗ FAIL: {description}")
            print(f"  Input: '{input_val}'")
            print(f"  Expected: city='{expected_city}', country={expected_country}")
            print(f"  Got:      city='{city}', country={country}")
            normalize_failed += 1
    except Exception as e:
        print(f"✗ ERROR: {description}")
        print(f"  Input: '{input_val}'")
        print(f"  Exception: {e}")
        normalize_failed += 1

print(f"\nNormalize Tests: {normalize_passed} passed, {normalize_failed} failed")

# ============================================================================
# PART 2: Test calculate_natal_chart() with various birthplace inputs
# ============================================================================

print("\n" + "=" * 80)
print("PART 2: Testing calculate_natal_chart() with birthplace variations")
print("=" * 80)

test_cases_calculation = [
    {
        "name": "Test Odesa (Ukrainian)",
        "profile": {
            "name": "Марія",
            "birth_date": "15.03.1990",
            "birth_time": "14:30",
            "birthplace": "Одеса"
        },
        "should_succeed": True
    },
    {
        "name": "Test Odesa (Ukrainian + Country)",
        "profile": {
            "name": "Марія",
            "birth_date": "15.03.1990",
            "birth_time": "14:30",
            "birthplace": "Одеса, Україна"
        },
        "should_succeed": True
    },
    {
        "name": "Test Odesa (English)",
        "profile": {
            "name": "Maria",
            "birth_date": "15.03.1990",
            "birth_time": "14:30",
            "birthplace": "Odesa"
        },
        "should_succeed": True
    },
    {
        "name": "Test Odesa (English + Country)",
        "profile": {
            "name": "Maria",
            "birth_date": "15.03.1990",
            "birth_time": "14:30",
            "birthplace": "Odesa, Ukraine"
        },
        "should_succeed": True
    },
    {
        "name": "Test Kyiv (Ukrainian)",
        "profile": {
            "name": "Іван",
            "birth_date": "20.05.1985",
            "birth_time": "10:15",
            "birthplace": "Київ"
        },
        "should_succeed": True
    },
    {
        "name": "Test invalid city",
        "profile": {
            "name": "Test",
            "birth_date": "01.01.1990",
            "birth_time": "12:00",
            "birthplace": "INVALID_NONEXISTENT_CITY_XYZ123"
        },
        "should_succeed": False
    },
    {
        "name": "Test London (valid English city)",
        "profile": {
            "name": "John",
            "birth_date": "25.12.1980",
            "birth_time": "08:45",
            "birthplace": "London"
        },
        "should_succeed": True
    },
]

calculation_passed = 0
calculation_failed = 0

for test_case in test_cases_calculation:
    name = test_case["name"]
    profile = test_case["profile"]
    should_succeed = test_case["should_succeed"]

    try:
        result = calculate_natal_chart(profile)
        
        if should_succeed:
            print(f"✓ PASS: {name}")
            print(f"  Birthplace: '{profile['birthplace']}'")
            print(f"  Result: {result['sun_sign']} Sun, {result['moon_sign']} Moon")
            calculation_passed += 1
        else:
            print(f"✗ FAIL: {name} - Should have raised AstrologyError but didn't")
            print(f"  Birthplace: '{profile['birthplace']}'")
            calculation_failed += 1
            
    except AstrologyError as e:
        if not should_succeed:
            print(f"✓ PASS: {name}")
            print(f"  Birthplace: '{profile['birthplace']}'")
            print(f"  Expected error raised: {str(e)[:70]}...")
            calculation_passed += 1
        else:
            print(f"✗ FAIL: {name}")
            print(f"  Birthplace: '{profile['birthplace']}'")
            print(f"  Unexpected AstrologyError: {e}")
            calculation_failed += 1
            
    except Exception as e:
        print(f"✗ ERROR: {name}")
        print(f"  Birthplace: '{profile['birthplace']}'")
        print(f"  Unexpected exception: {type(e).__name__}: {e}")
        calculation_failed += 1

print(f"\nCalculation Tests: {calculation_passed} passed, {calculation_failed} failed")

# ============================================================================
# SUMMARY
# ============================================================================

print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)

total_passed = normalize_passed + calculation_passed
total_failed = normalize_failed + calculation_failed
total_tests = total_passed + total_failed

print(f"Total: {total_passed}/{total_tests} tests passed")

if total_failed == 0:
    print("✓ All tests passed!")
    sys.exit(0)
else:
    print(f"✗ {total_failed} tests failed")
    sys.exit(1)
