import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


LOGGER = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "astroai.db"


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_profiles (
                telegram_user_id INTEGER PRIMARY KEY,
                telegram_username TEXT,
                name TEXT NOT NULL,
                birth_date TEXT NOT NULL,
                birth_time TEXT NOT NULL,
                birthplace TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS city_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                city_key TEXT NOT NULL,
                country_key TEXT NOT NULL DEFAULT '',
                city_name TEXT,
                country_code TEXT,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                timezone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (city_key, country_key)
            )
            """
        )

    LOGGER.info("Database initialized at %s", DB_PATH)


def get_cached_city(city_key: str, country_key: str) -> dict | None:
    """Retrieve cached geocoding data for a city.

    Args:
        city_key: Normalized (casefolded) city name used as cache key.
        country_key: Normalized (casefolded) country code, or empty string.

    Returns:
        dict with city_name, country_code, latitude, longitude, timezone,
        or None if not cached.
    """
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT city_name, country_code, latitude, longitude, timezone
            FROM city_cache
            WHERE city_key = ? AND country_key = ?
            """,
            (city_key, country_key),
        ).fetchone()

    if row is None:
        return None
    return dict(row)


def save_city_to_cache(
    city_key: str,
    country_key: str,
    city_name: str,
    country_code: str | None,
    latitude: float,
    longitude: float,
    tz_str: str,
) -> None:
    """Save resolved geocoding data to city cache.

    Upserts: updates existing entry if (city_key, country_key) already exists.

    Args:
        city_key: Normalized (casefolded) city name used as cache key.
        country_key: Normalized (casefolded) country code, or empty string.
        city_name: Human-readable city name (canonical form).
        country_code: Resolved country code string, or None.
        latitude: Resolved latitude.
        longitude: Resolved longitude.
        tz_str: IANA timezone string (e.g. "Europe/Kyiv").
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO city_cache (
                city_key, country_key, city_name, country_code,
                latitude, longitude, timezone, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(city_key, country_key) DO UPDATE SET
                city_name     = excluded.city_name,
                country_code  = excluded.country_code,
                latitude      = excluded.latitude,
                longitude     = excluded.longitude,
                timezone      = excluded.timezone,
                updated_at    = excluded.updated_at
            """,
            (
                city_key,
                country_key,
                city_name,
                country_code or "",
                latitude,
                longitude,
                tz_str,
                timestamp,
                timestamp,
            ),
        )
    LOGGER.debug("Saved city to cache: city_key=%s country_key=%s", city_key, country_key)


def upsert_user_profile(
    telegram_user_id: int,
    telegram_username: str | None,
    name: str,
    birth_date: str,
    birth_time: str,
    birthplace: str,
) -> None:
    timestamp = datetime.now(timezone.utc).isoformat()

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO user_profiles (
                telegram_user_id,
                telegram_username,
                name,
                birth_date,
                birth_time,
                birthplace,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
                telegram_username = excluded.telegram_username,
                name = excluded.name,
                birth_date = excluded.birth_date,
                birth_time = excluded.birth_time,
                birthplace = excluded.birthplace,
                updated_at = excluded.updated_at
            """,
            (
                telegram_user_id,
                telegram_username,
                name,
                birth_date,
                birth_time,
                birthplace,
                timestamp,
                timestamp,
            ),
        )


def get_user_profile(telegram_user_id: int) -> dict | None:
    with get_connection() as connection:
        row = connection.execute(
            """
            SELECT
                telegram_user_id,
                telegram_username,
                name,
                birth_date,
                birth_time,
                birthplace,
                created_at,
                updated_at
            FROM user_profiles
            WHERE telegram_user_id = ?
            """,
            (telegram_user_id,),
        ).fetchone()

    if row is None:
        return None

    return dict(row)