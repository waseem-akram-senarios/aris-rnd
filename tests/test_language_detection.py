import sys
import os

# Add project root to path
sys.path.append('/home/senarios/Desktop/aris')

from services.language.detector import get_detector

def test_detection(text):
    detector = get_detector()
    result = detector.detect(text)
    name = detector.get_language_name(result)
    print(f"Text: '{text}'")
    print(f"Detected: {result} ({name})")
    print("-" * 20)

test_cases = [
    "What is the contact email?",
    "¿Cuál es el correo de contacto?",
    "Donde esta el motor?",
    "Como se limpia la maquina?",
    "Procedimiento de degasado",
    "Hola, como estas?",
    "Tell me about the system"
]

for tc in test_cases:
    test_detection(tc)
