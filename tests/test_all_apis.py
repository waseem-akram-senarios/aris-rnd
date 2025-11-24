#!/usr/bin/env python3
"""
Test script for all API keys in .env file
"""
import os
import sys
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

print("=" * 60)
print("API Keys Test Suite")
print("=" * 60)

# Test OpenAI API
print("\n🔵 Testing OpenAI API...")
openai_key = os.getenv('OPENAI_API_KEY')
if openai_key:
    print(f"   Key prefix: {openai_key[:20]}...")
    try:
        headers = {"Authorization": f"Bearer {openai_key}"}
        response = requests.get("https://api.openai.com/v1/models", headers=headers, timeout=10)
        if response.status_code == 200:
            models = response.json()
            print(f"   ✅ OpenAI API: Working ({len(models.get('data', []))} models)")
        else:
            print(f"   ❌ OpenAI API: Failed (Status {response.status_code})")
    except Exception as e:
        print(f"   ❌ OpenAI API: Error - {str(e)[:50]}")
else:
    print("   ⚠️  OpenAI API key not found")

# Test Cerebras API
print("\n🟢 Testing Cerebras API...")
cerebras_key = os.getenv('CEREBRAS_API_KEY')
if cerebras_key:
    print(f"   Key prefix: {cerebras_key[:20]}...")
    try:
        headers = {"Authorization": f"Bearer {cerebras_key}"}
        response = requests.get("https://api.cerebras.ai/v1/models", headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            models = data.get('data', [])
            print(f"   ✅ Cerebras API: Working ({len(models)} models)")
        else:
            print(f"   ❌ Cerebras API: Failed (Status {response.status_code})")
    except Exception as e:
        print(f"   ❌ Cerebras API: Error - {str(e)[:50]}")
else:
    print("   ⚠️  Cerebras API key not found")

print("\n" + "=" * 60)
print("Test completed!")
print("=" * 60)

