#!/usr/bin/env python3
"""
Test script to verify OCR is in Streamlit UI
Run this to check if your UI has OCR integration
"""

import sys
import re

print("=" * 60)
print("Testing Streamlit UI for OCR Integration")
print("=" * 60)
print()

# Read the UI file
try:
    with open('api/app.py', 'r') as f:
        content = f.read()
except FileNotFoundError:
    print("❌ ERROR: api/app.py not found!")
    print("   Make sure you're in the project root directory")
    sys.exit(1)

# Test 1: Check parser dropdown
print("Test 1: Checking parser dropdown...")
match = re.search(r'st\.selectbox\([^)]*"Choose Parser:"[^)]*\[(.*?)\]', content, re.DOTALL)
if match:
    parsers_str = match.group(1)
    parsers = [p.strip().strip('"').strip("'") for p in parsers_str.split(',')]
    print(f"  Found parsers: {parsers}")
    
    if 'OCRmyPDF' in parsers:
        print("  ✅ OCRmyPDF is in the dropdown")
    else:
        print("  ❌ OCRmyPDF NOT in dropdown")
        print("  Available parsers:", parsers)
else:
    print("  ❌ Could not find parser dropdown")

# Test 2: Check OCR settings panel
print()
print("Test 2: Checking OCR settings panel...")
if 'if parser_choice == "OCRmyPDF"' in content:
    print("  ✅ OCR settings panel code found")
else:
    print("  ❌ OCR settings panel NOT found")

# Test 3: Check OCR language input
print()
print("Test 3: Checking OCR language input...")
if 'ocr_languages' in content:
    print("  ✅ OCR language input found")
else:
    print("  ❌ OCR language input NOT found")

# Test 4: Check DPI slider
print()
print("Test 4: Checking DPI slider...")
if 'ocr_dpi' in content:
    print("  ✅ DPI slider found")
else:
    print("  ❌ DPI slider NOT found")

# Test 5: Find line numbers
print()
print("Test 5: Finding OCR code locations...")
lines = content.split('\n')
for i, line in enumerate(lines, 1):
    if 'OCRmyPDF' in line and 'selectbox' in lines[max(0, i-5):i+5]:
        print(f"  Parser dropdown at line: {i}")
    if 'if parser_choice == "OCRmyPDF"' in line:
        print(f"  OCR settings panel at line: {i}")

print()
print("=" * 60)
print("Summary:")
print("=" * 60)

# Count OCRmyPDF mentions
ocr_count = content.count('OCRmyPDF')
print(f"Total 'OCRmyPDF' mentions in file: {ocr_count}")

if ocr_count >= 3:
    print()
    print("✅ OCR integration IS in your UI file!")
    print()
    print("If you can't see it in Streamlit:")
    print("1. Stop Streamlit (Ctrl+C)")
    print("2. Clear cache: rm -rf .streamlit/cache")
    print("3. Restart: streamlit run api/app.py")
    print("4. Look in SIDEBAR → 'Parser Settings'")
    print("5. Click the dropdown")
    print("6. Select 'OCRmyPDF'")
else:
    print()
    print("❌ OCR integration might be incomplete")
    print("   Expected at least 3 mentions, found:", ocr_count)

print()
