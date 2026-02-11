#!/usr/bin/env python3
"""
Manual test of image search functionality
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

# Server configuration
SERVER_DOMAIN = "search-intelycx-waseem-os-4e6bsxzyull4zxtvxul5keh4wu.us-east-2.es.amazonaws.com"
BASE_URL = f"https://{SERVER_DOMAIN}"

# Create auth
access_key = os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID')
secret_key = os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
region = os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')

print(f"Access Key: {access_key[:10]}..." if access_key else "No Access Key")
print(f"Secret Key: {secret_key[:10]}..." if secret_key else "No Secret Key")

if not access_key or not secret_key:
    print("❌ Missing credentials")
    exit(1)

try:
    from requests_aws4auth import AWS4Auth
    awsauth = AWS4Auth(access_key, secret_key, region, 'es')
    print("✅ AWS4Auth created successfully")
except Exception as e:
    print(f"❌ Failed to create AWS4Auth: {e}")
    exit(1)

print("🔍 Testing image search...")

# Test image search
search_query = {
    "query": {"match_all": {}},
    "size": 3
}

try:
    response = requests.post(
        f"{BASE_URL}/aris-rag-images-index/_search",
        json=search_query,
        auth=awsauth,
        timeout=30
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        results = response.json()
        hits = results.get('hits', {}).get('hits', [])
        print(f"✅ Found {len(hits)} images")
        
        if hits:
            for i, hit in enumerate(hits[:3]):
                doc = hit['_source']
                print(f"\nImage {i+1}:")
                print(f"  Score: {hit.get('_score', 0)}")
                
                # Check available fields
                for key in doc.keys():
                    if key not in ['vector']:
                        value = str(doc[key])[:100]
                        print(f"  {key}: {value}...")
    else:
        print(f"❌ Failed: {response.text}")
        
except Exception as e:
    print(f"❌ Error: {e}")

print("\n🔍 Testing document search...")

# Test document search
try:
    response = requests.post(
        f"{BASE_URL}/aris-rag-index/_search",
        json=search_query,
        auth=awsauth,
        timeout=30
    )
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        results = response.json()
        hits = results.get('hits', {}).get('hits', [])
        print(f"✅ Found {len(hits)} documents")
        
        if hits:
            for i, hit in enumerate(hits[:3]):
                doc = hit['_source']
                print(f"\nDocument {i+1}:")
                print(f"  Score: {hit.get('_score', 0)}")
                content = doc.get('content', '')[:100]
                print(f"  Content: {content}...")
    else:
        print(f"❌ Failed: {response.text}")
        
except Exception as e:
    print(f"❌ Error: {e}")
