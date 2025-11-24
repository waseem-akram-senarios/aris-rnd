#!/usr/bin/env python3
"""
Test script for Cerebras API key
"""
import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API key from environment
api_key = os.getenv('CEREBRAS_API_KEY')

if not api_key:
    print("❌ Error: CEREBRAS_API_KEY not found in .env file")
    sys.exit(1)

print("✅ Cerebras API Key loaded from .env file")
print(f"🔑 Key prefix: {api_key[:20]}...")

# Test API connection using Cerebras SDK
print("\n🧪 Testing Cerebras API connection...")
try:
    # Try using the Cerebras SDK first
    try:
        from cerebras.cloud.sdk import Cerebras
        
        print("   Using Cerebras Python SDK...")
        client = Cerebras(api_key=api_key)
        
        # Test by listing models
        models = client.models.list()
        print(f"✅ API connection successful!")
        print(f"📊 Available models: {len(models)} models found")
        print(f"\n📋 Sample models:")
        for model in list(models)[:5]:
            model_id = model.get('id', model.get('name', 'N/A'))
            print(f"   - {model_id}")
        
    except ImportError:
        print("   Cerebras SDK not installed, trying direct API call...")
        import requests
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Try Cerebras API endpoints
        endpoints = [
            "https://api.cerebras.ai/v1/models",
            "https://api.cerebras.com/v1/models",
        ]
        
        success = False
        for endpoint in endpoints:
            try:
                print(f"   Trying: {endpoint}")
                response = requests.get(endpoint, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    print(f"✅ API connection successful!")
                    data = response.json()
                    if isinstance(data, dict) and 'data' in data:
                        models = data['data']
                        print(f"📊 Available models: {len(models)} models found")
                        for model in models[:5]:
                            print(f"   - {model.get('id', 'N/A')}")
                    else:
                        print(f"📊 Response: {response.text[:200]}...")
                    success = True
                    break
                elif response.status_code == 401:
                    print(f"❌ Authentication failed (401) - key may be invalid")
                    print(f"   Response: {response.text[:200]}")
                else:
                    print(f"⚠️  Status code: {response.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"   Connection error: {str(e)[:50]}")
                continue
        
        if not success:
            print("\n⚠️  Could not verify API key automatically.")
            print("   The key format looks correct, but endpoint testing failed.")
            print("   Install SDK: pip install cerebras-cloud-sdk")
            sys.exit(1)
            
except Exception as e:
    print(f"❌ Error testing Cerebras API: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n✅ Cerebras API key test completed!")

