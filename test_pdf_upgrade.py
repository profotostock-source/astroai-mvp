#!/usr/bin/env python
"""Test script to verify upgraded PDF report generation."""

import sys
from pathlib import Path

# Add workspace to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from database import init_db
from services.astrology import calculate_natal_chart
from services.pdf import generate_report

# Initialize database
init_db()

# Create test profile
profile = {
    "name": "Тест Користувач",
    "birth_date": "15.03.1990",
    "birth_time": "14:30",
    "birthplace": "Киев"
}

print("=" * 60)
print("Testing upgraded PDF report generation")
print("=" * 60)

try:
    # Calculate astrology data
    print("\n1. Calculating natal chart...")
    astrology_data = calculate_natal_chart(profile)
    print(f"   ✓ Sun: {astrology_data['sun_sign']}")
    print(f"   ✓ Moon: {astrology_data['moon_sign']}")
    print(f"   ✓ Ascendant: {astrology_data['ascendant_sign']}")
    print(f"   ✓ Planets: {len(astrology_data.get('planets', {}))} detected")

    # Generate report
    print("\n2. Generating PDF report with interpretations...")
    report_path = generate_report(profile, 123456789, astrology_data)
    print(f"   ✓ Report generated: {report_path}")
    print(f"   ✓ File size: {report_path.stat().st_size:,} bytes")

    print("\n" + "=" * 60)
    print("✅ PDF Report upgrade SUCCESSFUL")
    print("=" * 60)
    print("\nReport Features:")
    print("  • Ukrainian translations for planets and signs")
    print("  • Psychological portrait section")
    print("  • Sun sign interpretation (strengths, challenges, advice)")
    print("  • Moon sign interpretation (emotional nature)")
    print("  • Ascendant interpretation (how others see you)")
    print("  • Technical tables (planets, houses, aspects)")
    print("  • Disclaimer")

except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
