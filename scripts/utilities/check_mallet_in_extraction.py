#!/usr/bin/env python3
"""Quick check if 'mallet' is in Docling extracted text"""
import sys
sys.path.insert(0, '.')

from parsers.docling_parser import DoclingParser

print("Parsing document to check for 'mallet'...")
parser = DoclingParser()
result = parser.parse('FL10.11 SPECIFIC8 (1).pdf')

text_lower = result.text.lower()
mallet_count = text_lower.count('mallet')

print(f"\n{'='*70}")
print(f"Search Results for 'mallet'")
print(f"{'='*70}")
print(f"Found: {mallet_count} occurrence(s)")

if mallet_count > 0:
    import re
    print(f"\n✅ 'mallet' IS in the extracted text!")
    
    # Find all occurrences
    matches = list(re.finditer(r'[^.]{0,150}mallet[^.]{0,150}', text_lower, re.IGNORECASE))
    print(f"\nContext around 'mallet' (showing all {len(matches)} matches):")
    for i, match in enumerate(matches, 1):
        context = match.group(0).strip()
        print(f"\n  Match {i}:")
        print(f"  {context[:300]}...")
    
    # Check if it's near image markers
    parts = result.text.split('<!-- image -->')
    print(f"\n{'='*70}")
    print(f"Checking if 'mallet' is in image content sections:")
    print(f"{'='*70}")
    
    found_in_images = []
    for i, part in enumerate(parts[1:], 1):
        if 'mallet' in part.lower():
            found_in_images.append(i)
            idx = part.lower().find('mallet')
            context = part[max(0, idx-150):idx+200]
            print(f"\n  ✅ Found in Image {i} content:")
            print(f"  ...{context}...")
    
    if found_in_images:
        print(f"\n✅ 'mallet' found in {len(found_in_images)} image(s): {found_in_images}")
    else:
        print(f"\n⚠️  'mallet' found in text but NOT in marked image sections")
        print(f"   This means it might be in one of the 9 images without markers")
else:
    print(f"\n❌ 'mallet' NOT found in extracted text")
    print(f"\nPossible reasons:")
    print(f"  1. OCR didn't recognize it (might be spelled differently)")
    print(f"  2. It's in one of the images that returned empty OCR results")
    print(f"  3. The image quality is too low for OCR")
    
    # Check for similar words
    print(f"\nChecking for similar words:")
    similar = ['hammer', 'mallot', 'malet', 'mallett']
    for word in similar:
        count = text_lower.count(word)
        if count > 0:
            print(f"  ✅ Found '{word}': {count} time(s)")

print(f"\n{'='*70}")
print(f"Summary:")
print(f"  Images detected: {result.image_count}")
print(f"  Markers inserted: {result.text.count('<!-- image -->')}")
print(f"  Text length: {len(result.text):,} characters")
print(f"  'mallet' found: {'✅ Yes' if mallet_count > 0 else '❌ No'}")
print(f"{'='*70}")

