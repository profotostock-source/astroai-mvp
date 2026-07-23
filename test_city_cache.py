# -*- coding: utf-8 -*-
"""Tests for city cache: normalization, CRUD, duplicate handling, and mock GeoNames skip."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure the project root is on the path when run directly
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Load .env so KERYKEION_GEONAMES_USERNAME is present for integration tests
from dotenv import load_dotenv
load_dotenv()

import database
from database import get_cached_city, init_db, save_city_to_cache
from services.astrology import (
    UKRAINIAN_CITY_ALIASES,
    _make_cache_keys,
    _CITY_ALIASES_CASEFOLDED,
    normalize_birthplace,
)


def _use_temp_db(test_func):
    """Decorator: redirect database.DB_PATH to a fresh temp file for one test."""
    def wrapper(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        original_path = database.DB_PATH
        try:
            database.DB_PATH = tmp_path
            init_db()
            test_func(self)
        finally:
            database.DB_PATH = original_path
            # Close all connections before deleting
            for conn in database.sqlite3.connect("").connection_cache.values() if hasattr(database.sqlite3.connect(""), "connection_cache") else []:
                try:
                    conn.close()
                except Exception:
                    pass
            import gc
            gc.collect()
            import time
            time.sleep(0.1)  # Give Windows time to release the lock
            try:
                tmp_path.unlink()
            except Exception:
                pass  # Ignore if it can't be deleted
    wrapper.__name__ = test_func.__name__
    return wrapper


class TestNormalizationOdesa(unittest.TestCase):
    """Verify all Odesa spelling variants resolve to canonical 'Odesa'."""

    ODESA_VARIANTS = [
        "Одеса",
        "Одесса",
        "odesa",
        "Odesa",
        "ODESA",
        "Odessa",
        "ODESSA",
    ]

    def test_odesa_variants_normalize_to_odesa(self):
        for variant in self.ODESA_VARIANTS:
            with self.subTest(variant=variant):
                city, _ = normalize_birthplace(variant)
                self.assertEqual(city, "Odesa", f"{variant!r} → expected 'Odesa', got {city!r}")

    def test_odesa_cache_keys_are_identical(self):
        """All Odesa variants produce the same cache key."""
        keys = set()
        for variant in self.ODESA_VARIANTS:
            city, country = normalize_birthplace(variant)
            ck, ctk = _make_cache_keys(city, country)
            keys.add(ck)
        self.assertEqual(len(keys), 1, f"Expected a single cache key, got: {keys}")

    def test_odesa_with_ukraine_country(self):
        city, country = normalize_birthplace("Odesa, Ukraine")
        self.assertEqual(city, "Odesa")
        self.assertEqual(country, "UA")


class TestNormalizationKyiv(unittest.TestCase):
    """Verify all Kyiv spelling variants resolve to canonical 'Kyiv'."""

    KYIV_VARIANTS = [
        "Київ",
        "Киев",
        "Kyiv",
        "kyiv",
        "KYIV",
        "Kiev",
        "KIEV",
    ]

    def test_kyiv_variants_normalize_to_kyiv(self):
        for variant in self.KYIV_VARIANTS:
            with self.subTest(variant=variant):
                city, _ = normalize_birthplace(variant)
                self.assertEqual(city, "Kyiv", f"{variant!r} → expected 'Kyiv', got {city!r}")

    def test_kyiv_cache_keys_are_identical(self):
        keys = set()
        for variant in self.KYIV_VARIANTS:
            city, country = normalize_birthplace(variant)
            ck, _ = _make_cache_keys(city, country)
            keys.add(ck)
        self.assertEqual(len(keys), 1, f"Expected a single cache key, got: {keys}")


class TestMakeCacheKeys(unittest.TestCase):
    def test_keys_are_casefolded(self):
        ck, ctk = _make_cache_keys("Odesa", "UA")
        self.assertEqual(ck, "odesa")
        self.assertEqual(ctk, "ua")

    def test_none_country_becomes_empty_string(self):
        ck, ctk = _make_cache_keys("London", None)
        self.assertEqual(ctk, "")

    def test_keys_are_str(self):
        ck, ctk = _make_cache_keys("Paris", "FR")
        self.assertIsInstance(ck, str)
        self.assertIsInstance(ctk, str)


class TestCacheCRUD(unittest.TestCase):
    """Test save_city_to_cache and get_cached_city using a temp database."""

    @_use_temp_db
    def test_save_and_retrieve(self):
        save_city_to_cache("london", "", "London", "GB", 51.5074, -0.1278, "Europe/London")
        cached = get_cached_city("london", "")
        self.assertIsNotNone(cached)
        self.assertAlmostEqual(cached["latitude"], 51.5074, places=4)
        self.assertAlmostEqual(cached["longitude"], -0.1278, places=4)
        self.assertEqual(cached["timezone"], "Europe/London")
        self.assertEqual(cached["country_code"], "GB")

    @_use_temp_db
    def test_missing_city_returns_none(self):
        result = get_cached_city("nonexistent", "")
        self.assertIsNone(result)

    @_use_temp_db
    def test_duplicate_upsert_updates_record(self):
        save_city_to_cache("paris", "fr", "Paris", "FR", 48.8566, 2.3522, "Europe/Paris")
        # Upsert with updated coordinates
        save_city_to_cache("paris", "fr", "Paris", "FR", 48.9000, 2.4000, "Europe/Paris")
        cached = get_cached_city("paris", "fr")
        self.assertIsNotNone(cached)
        self.assertAlmostEqual(cached["latitude"], 48.9000, places=4)

    @_use_temp_db
    def test_different_country_keys_stored_separately(self):
        save_city_to_cache("odesa", "",   "Odesa", "UA", 46.4825, 30.7233, "Europe/Kyiv")
        save_city_to_cache("odesa", "ua", "Odesa", "UA", 46.4825, 30.7233, "Europe/Kyiv")
        r1 = get_cached_city("odesa", "")
        r2 = get_cached_city("odesa", "ua")
        self.assertIsNotNone(r1)
        self.assertIsNotNone(r2)

    @_use_temp_db
    def test_city_name_stored_correctly(self):
        save_city_to_cache("odesa", "ua", "Odesa", "UA", 46.4825, 30.7233, "Europe/Kyiv")
        cached = get_cached_city("odesa", "ua")
        self.assertEqual(cached["city_name"], "Odesa")


class TestCacheHitSkipsGeoNames(unittest.TestCase):
    """Verify that a cache hit causes AstrologicalSubject to be called with online=False."""

    @_use_temp_db
    def test_cache_hit_uses_offline_subject(self):
        # Pre-populate cache
        save_city_to_cache("odesa", "", "Odesa", "UA", 46.4825, 30.7233, "Europe/Kyiv")

        profile = {
            "name": "Test",
            "birth_date": "01.01.1990",
            "birth_time": "12:00",
            "birthplace": "Odesa",
        }

        captured_kwargs = {}

        real_subject_cls = None
        try:
            from kerykeion import AstrologicalSubject as _RealSubject
            real_subject_cls = _RealSubject
        except ImportError:
            self.skipTest("kerykeion not installed")

        def fake_subject(*args, **kwargs):
            captured_kwargs.update(kwargs)
            # Delegate to real class so the rest of the function works
            return real_subject_cls(*args, **kwargs)

        with patch("services.astrology.AstrologicalSubject", side_effect=fake_subject):
            from services.astrology import calculate_natal_chart
            try:
                calculate_natal_chart(profile)
            except Exception:
                pass  # We only care about the kwargs captured

        self.assertIn("online", captured_kwargs,
                      "Expected AstrologicalSubject to be called with 'online' kwarg on cache HIT")
        self.assertFalse(captured_kwargs["online"],
                         "Expected online=False on cache HIT")
        self.assertNotIn("geonames_username", captured_kwargs,
                         "GeoNames username should NOT be passed when using cached coords (online=False)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
