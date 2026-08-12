"""Standalone visual check for the redesigned PDF report.

Generates reports/report_999001.pdf from mock natal-chart data, so the layout
can be reviewed without Telegram, geocoding or a live user profile.

Run:
    .venv\\Scripts\\activate
    python test_new_pdf.py

Set OPENAI_API_KEY in .env to exercise the real AI section; without it the
module falls back to its built-in message and the rest of the report still
renders.
"""

import sys
import traceback

from services.pdf_report import generate_report

PROFILE = {
    "name": "Олена Ковальчук",
    "birth_date": "14.03.1991",
    "birth_time": "08:25",
    "birthplace": "Львів, Україна",
}

ASTROLOGY_DATA = {
    "sun_sign": "Pis",
    "moon_sign": "Sco",
    "ascendant_sign": "Gem",
    "birth_time_known": True,
    # Same shape as services.astrology._extract_planets_data returns:
    # a dict keyed by lowercase planet name.
    "planets": {
        "sun": {"sign": "Pis", "degree": 23.4, "retrograde": False},
        "moon": {"sign": "Sco", "degree": 11.2, "retrograde": False},
        "mercury": {"sign": "Ari", "degree": 2.9, "retrograde": True},
        "venus": {"sign": "Aqu", "degree": 17.8, "retrograde": False},
        "mars": {"sign": "Cap", "degree": 5.1, "retrograde": False},
        "jupiter": {"sign": "Leo", "degree": 28.6, "retrograde": False},
        "saturn": {"sign": "Aqu", "degree": 9.3, "retrograde": False},
    },
    "houses": [],
    "aspects": [],
    "warnings": [],
}


def main() -> int:
    try:
        path = generate_report(PROFILE, 999001, ASTROLOGY_DATA)
    except Exception:
        traceback.print_exc()
        print("\nFAILED - see traceback above")
        return 1

    print(f"OK - report written to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
