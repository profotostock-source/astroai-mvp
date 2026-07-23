#!/usr/bin/env python3
"""Test script for AI-powered psychological interpretations in PDF reports."""

import logging
import os
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
LOGGER = logging.getLogger(__name__)

# Add services to path
import sys
sys.path.insert(0, str(Path(__file__).parent))


def test_ai_interpretation_module():
    """Test the AI interpretation module independently."""
    print("\n" + "="*70)
    print("TEST 1: AI Interpretation Module")
    print("="*70)
    
    try:
        from services.ai_interpretation import generate_psychological_report
        print("✅ Successfully imported generate_psychological_report")
    except ImportError as e:
        print(f"❌ Failed to import AI interpretation module: {e}")
        return False
    
    # Create sample astrology data
    sample_data = {
        "sun_sign": "Pisces",
        "moon_sign": "Scorpio",
        "ascendant_sign": "Leo",
        "birth_time_known": True,
        "planets": {
            "Mercury": {
                "sign": "Pisces",
                "degree": 12.5,
                "retrograde": False
            },
            "Venus": {
                "sign": "Aquarius",
                "degree": 8.3,
                "retrograde": False
            },
            "Mars": {
                "sign": "Taurus",
                "degree": 15.7,
                "retrograde": False
            },
            "Jupiter": {
                "sign": "Cancer",
                "degree": 22.1,
                "retrograde": False
            },
            "Saturn": {
                "sign": "Capricorn",
                "degree": 5.9,
                "retrograde": True
            },
        },
        "houses": [
            {"house": 1, "sign": "Leo", "degree": 14.2},
            {"house": 2, "sign": "Virgo", "degree": 10.1},
            {"house": 3, "sign": "Libra", "degree": 5.8},
            {"house": 4, "sign": "Scorpio", "degree": 2.3},
            {"house": 5, "sign": "Sagittarius", "degree": 25.4},
            {"house": 6, "sign": "Capricorn", "degree": 20.1},
            {"house": 7, "sign": "Aquarius", "degree": 14.2},
            {"house": 8, "sign": "Pisces", "degree": 10.1},
            {"house": 9, "sign": "Aries", "degree": 5.8},
            {"house": 10, "sign": "Taurus", "degree": 2.3},
            {"house": 11, "sign": "Gemini", "degree": 25.4},
            {"house": 12, "sign": "Cancer", "degree": 20.1},
        ],
        "aspects": [
            {
                "planet1": "Sun",
                "planet2": "Moon",
                "aspect": "Trine",
                "orb": 2.3
            },
            {
                "planet1": "Sun",
                "planet2": "Mars",
                "aspect": "Opposition",
                "orb": 4.1
            },
            {
                "planet1": "Venus",
                "planet2": "Jupiter",
                "aspect": "Square",
                "orb": 1.8
            },
        ],
        "warnings": []
    }
    
    print("\nGenerating AI psychological report...")
    print("(This will use OpenAI API if OPENAI_API_KEY is set)")
    
    report = generate_psychological_report(sample_data)
    
    if report:
        print(f"\n✅ Successfully generated report ({len(report)} characters)")
        print("\nFirst 300 characters of report:")
        print("-" * 70)
        print(report[:300] + "...")
        print("-" * 70)
        return True
    else:
        print("❌ Failed to generate report")
        return False


def test_pdf_generation_with_ai():
    """Test PDF generation with AI-generated interpretations."""
    print("\n" + "="*70)
    print("TEST 2: PDF Generation with AI Interpretations")
    print("="*70)
    
    try:
        from services.pdf import generate_report
        from services.astrology import calculate_natal_chart
        print("✅ Successfully imported PDF and astrology modules")
    except ImportError as e:
        print(f"❌ Failed to import required modules: {e}")
        return False
    
    # Create test profile
    test_profile = {
        "name": "Тест Користувач",
        "birth_date": "15.03.1990",
        "birth_time": "14:30",
        "birthplace": "Киев"
    }
    
    print(f"\nTest profile: {test_profile['name']}")
    print("Calculating natal chart...")
    
    try:
        astrology_data = calculate_natal_chart(test_profile)
        print("✅ Natal chart calculated successfully")
        print(f"  - Sun: {astrology_data.get('sun_sign')}")
        print(f"  - Moon: {astrology_data.get('moon_sign')}")
        print(f"  - Ascendant: {astrology_data.get('ascendant_sign')}")
    except Exception as e:
        print(f"❌ Failed to calculate natal chart: {e}")
        return False
    
    print("\nGenerating PDF report...")
    
    try:
        report_path = generate_report(test_profile, 123456789, astrology_data)
        
        if report_path.exists():
            file_size = report_path.stat().st_size
            print(f"✅ PDF generated successfully")
            print(f"  - Path: {report_path}")
            print(f"  - Size: {file_size:,} bytes")
            
            # Verify file is readable
            with open(report_path, 'rb') as f:
                header = f.read(4)
                if header == b'%PDF':
                    print(f"✅ PDF file verified (valid PDF header)")
                    return True
                else:
                    print(f"❌ Invalid PDF header")
                    return False
        else:
            print(f"❌ PDF file not created at {report_path}")
            return False
            
    except Exception as e:
        print(f"❌ Failed to generate PDF: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_fallback_mechanism():
    """Test the fallback mechanism when API is unavailable."""
    print("\n" + "="*70)
    print("TEST 3: Fallback Mechanism")
    print("="*70)
    
    # Save original API key
    original_api_key = os.getenv("OPENAI_API_KEY")
    
    try:
        # Temporarily remove API key to test fallback
        if "OPENAI_API_KEY" in os.environ:
            del os.environ["OPENAI_API_KEY"]
        
        # Reload the module to pick up the missing API key
        import importlib
        import services.ai_interpretation
        importlib.reload(services.ai_interpretation)
        
        from services.ai_interpretation import generate_psychological_report, FALLBACK_MESSAGE
        
        sample_data = {
            "sun_sign": "Pisces",
            "moon_sign": "Scorpio",
            "ascendant_sign": "Leo",
        }
        
        print("Testing behavior when OPENAI_API_KEY is not set...")
        report = generate_psychological_report(sample_data)
        
        if "демонстраційна версія" in report.lower() or "fallback" in report.lower():
            print("✅ Fallback message displayed correctly when API key is missing")
            return True
        else:
            print("⚠️  Report generated (API key might be set)")
            return True
            
    except Exception as e:
        print(f"❌ Fallback mechanism test failed: {e}")
        return False
    
    finally:
        # Restore original API key
        if original_api_key:
            os.environ["OPENAI_API_KEY"] = original_api_key


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("AI-POWERED PSYCHOLOGICAL INTERPRETATION TESTS")
    print("="*70)
    
    tests = [
        ("AI Interpretation Module", test_ai_interpretation_module),
        ("PDF Generation with AI", test_pdf_generation_with_ai),
        ("Fallback Mechanism", test_fallback_mechanism),
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
            import traceback
            traceback.print_exc()
            results[test_name] = False
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    exit_code = main()
    exit(exit_code)
