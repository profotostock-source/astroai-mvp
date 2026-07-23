# -*- coding: utf-8 -*-
"""Test case-insensitive normalize_birthplace() fix."""

from services.astrology import normalize_birthplace

cases = [
    ("odesa",           "Odesa",  None,      "odesa (lowercase English)"),
    ("ODESA",           "Odesa",  None,      "ODESA (uppercase English)"),
    ("одеса",           "Odesa",  None,      "одеса (lowercase Ukrainian)"),
    ("ОДЕСА",           "Odesa",  None,      "ОДЕСА (uppercase Ukrainian)"),
    ("Одеса",           "Odesa",  None,      "Одеса (canonical Ukrainian)"),
    ("одесса",          "Odesa",  None,      "одесса (lowercase Russian)"),
    ("Одесса",          "Odesa",  None,      "Одесса (Russian spelling)"),
    ("Odesa, Ukraine",  "Odesa",  "Ukraine", "Odesa with country"),
    ("Київ",            "Kyiv",   None,      "Київ"),
    ("київ",            "Kyiv",   None,      "київ (lowercase)"),
    ("KYIV",            "Kyiv",   None,      "KYIV (uppercase)"),
    ("Lviv",            "Lviv",   None,      "Lviv (canonical English)"),
    ("lviv",            "Lviv",   None,      "lviv (lowercase English)"),
    ("Харків",          "Kharkiv",None,      "Харків"),
    ("Дніпро",          "Dnipro", None,      "Дніпро"),
    ("Paris",           "Paris",  None,      "Paris (non-Ukrainian city)"),
    ("INVALID_XYZ",     "INVALID_XYZ", None, "Invalid city (unchanged)"),
]

passed = failed = 0
for inp, exp_city, exp_country, desc in cases:
    city, country = normalize_birthplace(inp)
    ok = city == exp_city and country == exp_country
    if ok:
        passed += 1
        print(f"PASS  {desc!r:50s}  ->  city={city!r}, country={country!r}")
    else:
        failed += 1
        print(f"FAIL  {desc!r:50s}")
        print(f"      Expected: city={exp_city!r}, country={exp_country!r}")
        print(f"      Got:      city={city!r}, country={country!r}")

print()
print(f"Results: {passed}/{passed + failed} passed, {failed} failed")
