#!/usr/bin/env python3
import sys
import os
import shutil
import subprocess
import requests
import importlib.util

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class Color:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_result(name, success, message=""):
    status = f"{Color.GREEN}OK{Color.END}" if success else f"{Color.RED}FAIL{Color.END}"
    print(f"[{status}] {Color.BOLD}{name:20}{Color.END} {message}")

def check_python_package(package_name):
    spec = importlib.util.find_spec(package_name)
    return spec is not None

def check_binary(binary_name):
    return shutil.which(binary_name) is not None

def main():
    print(f"\n{Color.BLUE}{Color.BOLD}=== Aris Parser Health Check ==={Color.END}\n")

    # 1. PyMuPDF (Default)
    pymupdf_ok = check_python_package("fitz")
    print_result("PyMuPDF", pymupdf_ok, "Required for the default high-accuracy parser")

    # 2. Tesseract (Core for OCR)
    tesseract_bin = check_binary("tesseract")
    tesseract_pkg = check_python_package("pytesseract")
    tesseract_ok = tesseract_bin and tesseract_pkg
    msg = ""
    if not tesseract_bin: msg += "tesseract-ocr binary missing. "
    if not tesseract_pkg: msg += "pytesseract package missing. "
    print_result("Tesseract OCR", tesseract_ok, msg or "Found and ready for OCR-based parsing")

    # 3. OCRmyPDF
    ocrmypdf_pkg = check_python_package("ocrmypdf")
    ocrmypdf_ok = ocrmypdf_pkg and tesseract_bin
    print_result("OCRmyPDF", ocrmypdf_ok, "Depends on Tesseract and ocrmypdf package")

    # 4. Docling
    docling_pkg = check_python_package("docling")
    print_result("Docling", docling_pkg, "Modern layout-aware parser")

    # 5. Ollama (for LlamaScan)
    ollama_server = os.environ.get("OLLAMA_SERVER_URL", "http://localhost:11434")
    try:
        resp = requests.get(f"{ollama_server}/api/tags", timeout=2)
        ollama_reachable = resp.status_code == 200
        models = [m.get("name") for m in resp.json().get("models", [])] if ollama_reachable else []
        model_name = os.environ.get("LLAMA_SCAN_MODEL", "llava:latest")
        model_found = any(model_name in m for m in models)
        
        ollama_ok = ollama_reachable and model_found
        ollama_msg = f"Connected to {ollama_server}."
        if not model_found: ollama_msg += f" Model '{model_name}' NOT FOUND."
    except Exception:
        ollama_ok = False
        ollama_msg = f"Could not connect to {ollama_server}"
    
    print_result("Ollama (LlamaScan)", ollama_ok, ollama_msg)

    print(f"\n{Color.BLUE}{Color.BOLD}=== Summary ==={Color.END}")
    if all([pymupdf_ok, tesseract_ok, ocrmypdf_ok, docling_pkg]):
        print(f"\n{Color.GREEN}✅ All core parsers are ready for server use!{Color.END}")
    else:
        print(f"\n{Color.YELLOW}⚠️  Some optional parsers are not fully configured.{Color.END}")
        print("Run 'sudo ./scripts/install_parser_dependencies.sh' to fix most issues.")

if __name__ == "__main__":
    main()
