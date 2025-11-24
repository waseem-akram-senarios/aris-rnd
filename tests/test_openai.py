#!/usr/bin/env python3
"""
Test script for OpenAI API key
"""
import os
import sys
from dotenv import load_dotenv
import requests

# Load environment variables
load_dotenv()

# Get API key from environment
api_key = os.getenv('OPENAI_API_KEY')

if not api_key:
    print("❌ Error: OPENAI_API_KEY not found in .env file")
    sys.exit(1)

print("✅ API Key loaded from .env file")
print(f"🔑 Key prefix: {api_key[:20]}...")

# Test API connection
print("\n🧪 Testing OpenAI API connection...")
try:
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    # Test 1: List models
    response = requests.get("https://api.openai.com/v1/models", headers=headers, timeout=10)
    
    if response.status_code == 200:
        models = response.json()
        print(f"✅ API connection successful!")
        print(f"📊 Available models: {len(models.get('data', []))} models found")
        print(f"\n📋 Sample models:")
        for model in models.get('data', [])[:5]:
            print(f"   - {model.get('id', 'N/A')}")
    else:
        print(f"❌ API connection failed with status code: {response.status_code}")
        print(f"Response: {response.text}")
        sys.exit(1)
        
except requests.exceptions.RequestException as e:
    print(f"❌ Error connecting to OpenAI API: {e}")
    sys.exit(1)

print("\n✅ All tests passed! Your OpenAI API key is working correctly.")


