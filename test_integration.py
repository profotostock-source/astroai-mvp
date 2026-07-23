#!/usr/bin/env python3
"""Integration test to debug the astrology PDF generation workflow."""

import logging
logging.basicConfig(level=logging.WARNING)

print("=" * 70)
print("ASTROLOGY PDF GENERATION DEBUG TEST")
print("=" * 70)

# Test 1: Check astrology module
print("\n[1] Testing calculate_natal_chart...")
try:
    from services.astrology import calculate_natal_chart
    
    profile = {
        'name': 'Test User',
        'birth_date': '15.03.1990',
        'birth_time': '14:30',
        'birthplace': 'London, UK'
    }
    
    astrology_data = calculate_natal_chart(profile)
    print(f"    ✓ Calculation successful")
    print(f"    ✓ Type: {type(astrology_data).__name__}")
    print(f"    ✓ Is dict: {isinstance(astrology_data, dict)}")
    print(f"    ✓ Keys: {list(astrology_data.keys())}")
    print(f"    ✓ Sun sign: {astrology_data.get('sun_sign')}")
    print(f"    ✓ Planets: {len(astrology_data.get('planets', {}))}")
    
except Exception as e:
    print(f"    ✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Test 2: Check if _build_astrology_section exists
print("\n[2] Testing _build_astrology_section exists...")
try:
    from services.pdf import _build_astrology_section
    print(f"    ✓ Function exists")
    print(f"    ✓ Is callable: {callable(_build_astrology_section)}")
except Exception as e:
    print(f"    ✗ ERROR: {e}")
    exit(1)

# Test 3: Check generate_report signature
print("\n[3] Testing generate_report signature...")
try:
    from services.pdf import generate_report
    import inspect
    
    sig = inspect.signature(generate_report)
    print(f"    ✓ Signature: {sig}")
    params = list(sig.parameters.keys())
    print(f"    ✓ Parameters: {params}")
    
    expected_params = ['profile', 'telegram_user_id', 'astrology_data']
    if params == expected_params:
        print(f"    ✓ Signature is CORRECT (has astrology_data parameter)")
    else:
        print(f"    ✗ Signature is WRONG! Expected {expected_params}, got {params}")
        exit(1)
    
except Exception as e:
    print(f"    ✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Test 4: Check if generate_report actually calls _build_astrology_section
print("\n[4] Checking if generate_report calls _build_astrology_section...")
try:
    import inspect
    from services.pdf import generate_report
    
    source = inspect.getsource(generate_report)
    if '_build_astrology_section' in source:
        print(f"    ✓ Function name found in generate_report source")
        if 'story.extend(_build_astrology_section' in source:
            print(f"    ✓ Function is being called with story.extend()")
        else:
            print(f"    ⚠ Function is referenced but might not be called correctly")
    else:
        print(f"    ✗ Function is NOT called in generate_report!")
        exit(1)
        
except Exception as e:
    print(f"    ✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Test 5: Try to generate a PDF
print("\n[5] Attempting to generate PDF...")
try:
    from services.pdf import generate_report
    from pathlib import Path
    
    report_path = generate_report(profile, 999, astrology_data)
    print(f"    ✓ PDF generated")
    print(f"    ✓ Path: {report_path}")
    print(f"    ✓ File exists: {report_path.exists()}")
    print(f"    ✓ File size: {report_path.stat().st_size} bytes")
    
    # Try to read PDF with PyPDF2
    try:
        import pypdf
        
        with open(report_path, 'rb') as f:
            pdf_reader = pypdf.PdfReader(f)
            num_pages = len(pdf_reader.pages)
            print(f"    ✓ PDF readable: {num_pages} pages")
            
            # Check if astrology section text appears in PDF
            found_astrology = False
            for page_num, page in enumerate(pdf_reader.pages):
                text = page.extract_text()
                if 'натальної карти' in text or 'Планети' in text or 'Основні' in text:
                    found_astrology = True
                    print(f"    ✓ Astrology section found on page {page_num + 1}")
                    
            if not found_astrology:
                print(f"    ✗ Astrology section NOT found in PDF!")
                print(f"    First page text preview:")
                print(pdf_reader.pages[0].extract_text()[:300])
                exit(1)
                
    except ImportError:
        print(f"    ⚠ pypdf not installed, skipping PDF text check")
    
except Exception as e:
    print(f"    ✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

print("\n" + "=" * 70)
print("✓ ALL TESTS PASSED!")
print("=" * 70)
