"""Application configuration: loads .env and validates required environment variables."""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

LOGGER = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN: str | None = os.getenv("TELEGRAM_BOT_TOKEN")

REPORT_PRICES_XTR = {
    "natal": int(os.getenv("PRICE_NATAL_XTR", "99")),
    "year": int(os.getenv("PRICE_YEAR_XTR", "99")),
    "together": int(os.getenv("PRICE_TOGETHER_XTR", "99")),
}
FREE_USER_IDS = {
    int(value.strip())
    for value in os.getenv("FREE_USER_IDS", "").split(",")
    if value.strip().isdigit()
}

ADMIN_USER_IDS = {
    int(value.strip())
    for value in os.getenv("ADMIN_USER_IDS", "382403468").split(",")
    if value.strip().isdigit()
}

SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "Nickolas_81").lstrip("@")

if not TELEGRAM_BOT_TOKEN:
    LOGGER.error(
        "TELEGRAM_BOT_TOKEN is not set. "
        "Add it to your .env file before starting the bot."
    )

if not os.getenv("KERYKEION_GEONAMES_USERNAME"):
    LOGGER.warning(
        "KERYKEION_GEONAMES_USERNAME is not set. "
        "GeoNames geocoding will use the shared demo account, which has strict "
        "daily rate limits and may cause chart calculation failures. "
        "Register a free account at https://www.geonames.org/login "
        "and add KERYKEION_GEONAMES_USERNAME to your .env file."
    )
