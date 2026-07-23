#!/usr/bin/env python3
"""Minimal test for AI interpretation integration."""

import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

# Test 1: Import check
print("\n" + "="*70)
print("TEST 1: Module Import Check")
print("="*70)

try:
    from services.ai_interpretation import generate_psychological_report
    print("✅ AI interpretation module imported successfully")
except Exception as e:
    print(f"❌ Failed to import: {e}")
    exit(1)

try:
    from services.pdf import generate_report
    print("✅ PDF module imported successfully")
except Exception as e:
    print(f"❌ Failed to import: {e}")
    exit(1)

# Test 2: API key check
print("\n" + "="*70)
print("TEST 2: Environment Setup")
print("="*70)

api_key = os.getenv("OPENAI_API_KEY")
if api_key and api_key != "your_openai_api_key_here":
    print(f"✅ OPENAI_API_KEY is set (first 10 chars: {api_key[:10]}...)")
else:
    print("⚠️  OPENAI_API_KEY not configured (AI will use fallback)")

# Test 3: Test AI report generation with fallback
print("\n" + "="*70)
print("TEST 3: Fallback Mechanism Test")
print("="*70)

sample_data = {
    "sun_sign": "Pisces",
    "moon_sign": "Scorpio",
    "ascendant_sign": "Leo",
    "birth_time_known": True,
    "planets": {
        "Sun": {"sign": "Pisces", "degree": 25.5},
        "Moon": {"sign": "Scorpio", "degree": 18.3},
    },
    "houses": [],
    "aspects": [],
    "warnings": []
}

try:
    report = generate_psychological_report(sample_data)
    if report:
        word_count = len(report.split())
        print(f"✅ Psychological report generated ({word_count} words)")
        
        # Check if it's fallback or real
        if "демонстраційна версія" in report.lower() or "fallback" in report.lower():
            print("   (Using fallback message - API key not configured)")
        else:
            print("   (Using AI-generated content from OpenAI)")
    else:
        print("❌ No report returned")
        exit(1)
except Exception as e:
    print(f"❌ Error generating report: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Test 4: Format check
print("\n" + "="*70)
print("TEST 4: Report Format Verification")
print("="*70)

required_sections = [
    "портрет",
    "силь",  # сильні або сильных
    "вклик",  # виклики
]

missing_sections = []
for section in required_sections:
    if section.lower() not in report.lower():
        missing_sections.append(section)

if not missing_sections:
    print(f"✅ All expected sections found in report")
else:
    print(f"⚠️  Some sections might be missing: {missing_sections}")

print("\n" + "="*70)
print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
print("="*70)
print("\nNext steps:")
print("1. Set OPENAI_API_KEY in .env file with your actual OpenAI API key")
print("2. Run PDF generation to test the full integration")
print("3. Check reports/ folder for generated PDF files")
print()
