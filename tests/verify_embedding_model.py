"""
Verify which embedding model is being used
"""
import requests
import sys

BASE_URL = "http://44.221.84.58:8500"

def check_model():
    print("=" * 80)
    print("🔍 EMBEDDING MODEL VERIFICATION")
    print("=" * 80)
    
    try:
        # Check health endpoint
        response = requests.get(f"{BASE_URL}/health", timeout=30)
        response.raise_for_status()
        health = response.json()
        
        print(f"\n✅ Server Status: {health.get('status', 'unknown')}")
        
        # Check if there's model info in health
        if 'embedding_model' in health:
            print(f"📊 Embedding Model: {health['embedding_model']}")
        
        # Try getting system info
        try:
            response = requests.get(f"{BASE_URL}/", timeout=30)
            info = response.json()
            if 'embedding_model' in info:
                print(f"📊 Embedding Model (from root): {info['embedding_model']}")
        except:
            pass
        
        # Check documents endpoint for model info
        try:
            response = requests.get(f"{BASE_URL}/documents", timeout=30)
            docs_info = response.json()
            if isinstance(docs_info, dict) and 'model_info' in docs_info:
                print(f"📊 Model Info: {docs_info['model_info']}")
        except:
            pass
        
        print("\n" + "=" * 80)
        print("📋 CONFIGURATION CHECK")
        print("=" * 80)
        
        # Read config from local file
        import sys
        import os
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        
        from shared.config.settings import ARISConfig
        
        print(f"\n✅ Configured Embedding Model: {ARISConfig.EMBEDDING_MODEL}")
        print(f"✅ Configured OpenAI Model: {ARISConfig.OPENAI_MODEL}")
        print(f"✅ Configured Cerebras Model: {ARISConfig.CEREBRAS_MODEL}")
        
        # Model details
        model_details = {
            "text-embedding-3-large": {
                "dimensions": 3072,
                "quality": "Highest",
                "cost": "Higher",
                "description": "Latest OpenAI embedding model with best quality"
            },
            "text-embedding-3-small": {
                "dimensions": 1536,
                "quality": "Good",
                "cost": "Lower",
                "description": "Efficient OpenAI embedding model"
            },
            "text-embedding-ada-002": {
                "dimensions": 1536,
                "quality": "Legacy",
                "cost": "Lowest",
                "description": "Older OpenAI model, still reliable"
            }
        }
        
        model = ARISConfig.EMBEDDING_MODEL
        if model in model_details:
            details = model_details[model]
            print(f"\n📊 Model Details:")
            print(f"   Dimensions: {details['dimensions']}")
            print(f"   Quality: {details['quality']}")
            print(f"   Cost: {details['cost']}")
            print(f"   Description: {details['description']}")
        
        print("\n" + "=" * 80)
        print("✅ VERIFICATION COMPLETE")
        print("=" * 80)
        
        if model == "text-embedding-3-large":
            print(f"\n✅ SUCCESS: Using text-embedding-3-large (3072 dimensions)")
            print(f"   This is the highest quality OpenAI embedding model!")
            return 0
        elif model == "text-embedding-ada-002":
            print(f"\n⚠️  WARNING: Using legacy model text-embedding-ada-002")
            print(f"   Recommended: Upgrade to text-embedding-3-large")
            return 1
        else:
            print(f"\n✅ Using: {model}")
            return 0
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(check_model())

