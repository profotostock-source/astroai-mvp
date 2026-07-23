"""Standalone debug script for testing calculate_natal_chart.

Run this script twice in sequence to observe:
  1st run: City cache MISS  -> GeoNames request -> city saved to cache
  2nd run: City cache HIT   -> no GeoNames request
"""

import os
import logging

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)

geonames_loaded = bool(os.getenv("KERYKEION_GEONAMES_USERNAME"))
print("GeoNames username loaded:", "YES" if geonames_loaded else "NO")

from database import init_db
from services.astrology import calculate_natal_chart

init_db()

profile = {
    "name": "Микола",
    "birth_date": "11.02.2000",
    "birth_time": "22:22",
    "birthplace": "odesa"
}


def run(label: str) -> None:
    print()
    print("=" * 60)
    print(f"  {label}")
    print("=" * 60)
    result = calculate_natal_chart(profile)
    print("sun_sign      :", result["sun_sign"])
    print("moon_sign     :", result["moon_sign"])
    print("ascendant_sign:", result["ascendant_sign"])
    print("planets       :", len(result["planets"]))
    print("houses        :", len(result["houses"]))


run("RUN 1 — expect cache MISS + GeoNames request")
run("RUN 2 — expect cache HIT, no GeoNames request")
