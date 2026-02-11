#!/usr/bin/env python3
"""
Quick server connectivity test for ARIS deployment
Tests OpenSearch and S3 connectivity
"""
import os
import httpx
import boto3
import json
from dotenv import load_dotenv

load_dotenv()

# Server configuration
SERVER_DOMAIN = "search-intelycx-waseem-os-4e6bsxzyull4zxtvxul5keh4wu.us-east-2.es.amazonaws.com"
BASE_URL = f"https://{SERVER_DOMAIN}"

def test_credentials():
    """Test that required credentials are available"""
    print("="*60)
    print("🔍 CHECKING CREDENTIALS")
    print("="*60)
    
    required_vars = {
        'AWS_OPENSEARCH_ACCESS_KEY_ID': 'OpenSearch Access Key',
        'AWS_OPENSEARCH_SECRET_ACCESS_KEY': 'OpenSearch Secret Key', 
        'AWS_OPENSEARCH_REGION': 'OpenSearch Region',
        'AWS_S3_BUCKET': 'S3 Bucket',
        'OPENAI_API_KEY': 'OpenAI API Key'
    }
    
    missing_vars = []
    for var, desc in required_vars.items():
        value = os.getenv(var)
        if value:
            print(f"✅ {desc}: {'*' * (len(value[:8]) + 2)}{value[-2:]}")
        else:
            print(f"❌ {desc}: MISSING")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n⚠️ Missing variables: {missing_vars}")
        return False
    else:
        print("\n✅ All credentials available!")
        return True

async def test_opensearch_connectivity():
    """Test OpenSearch connectivity"""
    print("\n" + "="*60)
    print("🔍 TESTING OPENSEARCH CONNECTIVITY")
    print("="*60)
    
    access_key = os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
    
    if not access_key or not secret_key:
        print("❌ OpenSearch credentials not available")
        return False
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Test cluster health
            print("📡 Testing cluster health...")
            response = await client.get(
                f"{BASE_URL}/_cluster/health",
                auth=(access_key, secret_key)
            )
            
            if response.status_code == 200:
                health = response.json()
                print(f"✅ Cluster Status: {health['status']}")
                print(f"   Nodes: {health['number_of_nodes']}")
                print(f"   Data Nodes: {health['number_of_data_nodes']}")
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
            
            # Test indices
            print("\n📚 Checking indices...")
            response = await client.get(
                f"{BASE_URL}/_cat/indices?format=json",
                auth=(access_key, secret_key)
            )
            
            if response.status_code == 200:
                indices = response.json()
                print(f"✅ Found {len(indices)} indices:")
                
                for idx in indices:
                    name = idx['index']
                    docs = idx['docs.count']
                    size = idx['store.size']
                    print(f"   - {name}: {docs} docs, {size}")
                    
                    # Check for ARIS indices
                    if 'aris-rag' in name:
                        print(f"     🎯 ARIS index detected!")
            else:
                print(f"❌ Failed to list indices: {response.status_code}")
                return False
            
            # Test search on main index
            print("\n🔍 Testing document search...")
            search_query = {
                "query": {"match_all": {}},
                "size": 3
            }
            
            response = await client.post(
                f"{BASE_URL}/aris-rag-index/_search",
                json=search_query,
                auth=(access_key, secret_key)
            )
            
            if response.status_code == 200:
                results = response.json()
                hits = results.get('hits', {}).get('hits', [])
                print(f"✅ Search successful: {len(hits)} documents found")
                
                if hits:
                    doc = hits[0]['_source']
                    metadata = doc.get('metadata', {})
                    source = metadata.get('source', 'Unknown')
                    page = metadata.get('page', 'N/A')
                    print(f"   Sample: {source} (Page {page})")
            else:
                print(f"⚠️ Search failed: {response.status_code}")
                # Don't fail - might be no documents yet
            
            return True
            
        except Exception as e:
            print(f"❌ OpenSearch connectivity error: {e}")
            return False

def test_s3_connectivity():
    """Test S3 connectivity"""
    print("\n" + "="*60)
    print("🔍 TESTING S3 CONNECTIVITY")
    print("="*60)
    
    try:
        # Get S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID') or os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY') or os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
        
        bucket_name = os.getenv('AWS_S3_BUCKET', 'intelycx-waseem-s3-bucket')
        print(f"📦 Testing bucket: {bucket_name}")
        
        # Test bucket access
        try:
            response = s3_client.head_bucket(Bucket=bucket_name)
            print("✅ Bucket access confirmed")
        except Exception as e:
            print(f"❌ Bucket access failed: {e}")
            return False
        
        # List documents
        print("\n📄 Listing documents...")
        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix='documents/', MaxKeys=10)
        
        if 'Contents' in response:
            documents = response['Contents']
            print(f"✅ Found {len(documents)} documents:")
            
            for doc in documents[:5]:
                key = doc['Key']
                size = doc['Size']
                last_mod = doc['LastModified'].strftime('%Y-%m-%d')
                print(f"   - {key} ({size} bytes, {last_mod})")
        else:
            print("ℹ️ No documents found in bucket")
        
        # Check for registry backup
        print("\n📋 Checking registry backup...")
        try:
            response = s3_client.head_object(
                Bucket=bucket_name, 
                Key='configs/document_registry.json'
            )
            print("✅ Registry backup found")
        except:
            print("ℹ️ No registry backup found")
        
        return True
        
    except Exception as e:
        print(f"❌ S3 connectivity error: {e}")
        return False

async def main():
    """Run all connectivity tests"""
    print("🚀 ARIS SERVER CONNECTIVITY TEST")
    print(f"🎯 Target: {SERVER_DOMAIN}")
    print("="*60)
    
    # Test credentials
    creds_ok = test_credentials()
    if not creds_ok:
        print("\n❌ Credential check failed. Exiting.")
        return
    
    # Test OpenSearch
    os_ok = await test_opensearch_connectivity()
    
    # Test S3
    s3_ok = test_s3_connectivity()
    
    # Summary
    print("\n" + "="*60)
    print("📊 TEST SUMMARY")
    print("="*60)
    print(f"Credentials: {'✅ OK' if creds_ok else '❌ FAIL'}")
    print(f"OpenSearch:  {'✅ OK' if os_ok else '❌ FAIL'}")
    print(f"S3:          {'✅ OK' if s3_ok else '❌ FAIL'}")
    
    overall_ok = creds_ok and os_ok and s3_ok
    print(f"\nOverall:     {'✅ ALL TESTS PASSED' if overall_ok else '❌ SOME TESTS FAILED'}")
    
    if overall_ok:
        print("\n🎉 Your ARIS server deployment is ready for E2E testing!")
        print("\nNext steps:")
        print("1. Run: pytest tests/e2e/test_server_endpoints.py -v -m server")
        print("2. Test document upload and query workflows")
        print("3. Verify image search functionality")
    else:
        print("\n⚠️ Fix the issues above before proceeding with E2E tests")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
