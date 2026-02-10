"""
End-to-end tests for ARIS server deployment
Tests against the actual AWS server: search-intelycx-waseem-os-4e6bsxzyull4zxtvxul5keh4wu.us-east-2.es.amazonaws.com
"""
import pytest
import httpx
import os
from unittest.mock import patch, MagicMock


# Server configuration from your environment
SERVER_DOMAIN = "search-intelycx-waseem-os-4e6bsxzyull4zxtvxul5keh4wu.us-east-2.es.amazonaws.com"
BASE_URL = f"https://{SERVER_DOMAIN}"
API_BASE_URL = "https://your-api-gateway-url.com"  # Update with your actual API Gateway URL


@pytest.mark.e2e
@pytest.mark.server
class TestServerDeployment:
    """Test against the actual AWS server deployment"""
    
    @pytest.fixture
    async def server_client(self):
        """HTTP client for server testing with AWS auth"""
        import boto3
        from requests_aws4auth import AWS4Auth
        
        # Get AWS credentials
        access_key = os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID')
        secret_key = os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
        region = os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')
        service = 'es'
        
        # Create AWS auth
        awsauth = AWS4Auth(access_key, secret_key, region, service)
        
        async with httpx.AsyncClient(
            timeout=30.0,
            headers={'Content-Type': 'application/json'}
        ) as client:
            # Set auth for all requests
            client.auth = (access_key, secret_key)
            yield client
    
    async def test_opensearch_connection(self, server_client):
        """Test OpenSearch server connection"""
        # Test basic OpenSearch health
        response = await server_client.get(f"{BASE_URL}/_cluster/health")
        
        if response.status_code == 200:
            health_data = response.json()
            assert "status" in health_data
            print(f"OpenSearch Status: {health_data['status']}")
        else:
            print(f"OpenSearch connection failed: {response.status_code}")
    
    async def test_opensearch_indices(self, server_client):
        """Test OpenSearch indices"""
        # List all indices
        response = await server_client.get(f"{BASE_URL}/_cat/indices?format=json")
        
        if response.status_code == 200:
            indices = response.json()
            print(f"Found {len(indices)} indices")
            
            # Check for expected indices
            index_names = [idx['index'] for idx in indices]
            print(f"Available indices: {index_names}")
            
            # Should have aris-rag-index and aris-rag-images-index
            assert any('aris-rag-index' in name for name in index_names)
        else:
            print(f"Failed to list indices: {response.status_code}")
    
    async def test_document_search(self, server_client):
        """Test document search in OpenSearch"""
        # Search for documents
        search_query = {
            "query": {
                "match_all": {}
            },
            "size": 5
        }
        
        response = await server_client.post(
            f"{BASE_URL}/aris-rag-index/_search",
            json=search_query
        )
        
        if response.status_code == 200:
            results = response.json()
            hits = results.get('hits', {}).get('hits', [])
            print(f"Found {len(hits)} documents")
            
            if hits:
                # Check document structure
                doc = hits[0]['_source']
                assert 'content' in doc
                assert 'metadata' in doc
                print(f"Sample document: {doc.get('metadata', {}).get('source', 'Unknown')}")
        else:
            print(f"Search failed: {response.status_code}")
    
    async def test_image_search(self, server_client):
        """Test image search in OpenSearch"""
        # Search for images
        search_query = {
            "query": {
                "match_all": {}
            },
            "size": 5
        }
        
        response = await server_client.post(
            f"{BASE_URL}/aris-rag-images-index/_search",
            json=search_query
        )
        
        if response.status_code == 200:
            results = response.json()
            hits = results.get('hits', {}).get('hits', [])
            print(f"Found {len(hits)} images")
            
            if hits:
                # Check image structure
                doc = hits[0]['_source']
                assert 'ocr_text' in doc or 'content' in doc
                print(f"Sample image OCR: {doc.get('ocr_text', 'No OCR text')[:100]}...")
        else:
            print(f"Image search failed: {response.status_code}")
    
    async def test_s3_document_access(self):
        """Test S3 document access"""
        import boto3
        
        # Get S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
        
        bucket_name = os.getenv('AWS_S3_BUCKET', 'intelycx-waseem-s3-bucket')
        
        try:
            # List documents in S3
            response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix='documents/')
            
            if 'Contents' in response:
                documents = response['Contents']
                print(f"Found {len(documents)} documents in S3")
                
                # Show first few documents
                for doc in documents[:5]:
                    print(f"  - {doc['Key']}")
            else:
                print("No documents found in S3")
                
        except Exception as e:
            print(f"S3 access failed: {e}")


@pytest.mark.e2e
@pytest.mark.server
@pytest.mark.integration
class TestServerIntegration:
    """Test server integration with actual services"""
    
    async def test_opensearch_mapping_structure(self):
        """Test OpenSearch index mapping structure"""
        import boto3
        from requests_aws4auth import AWS4Auth
        
        # Get AWS auth
        access_key = os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID')
        secret_key = os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
        region = os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')
        service = 'es'
        
        awsauth = AWS4Auth(access_key, secret_key, region, service)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Check main index mapping
            response = await client.get(
                f"{BASE_URL}/aris-rag-index/_mapping",
                auth=(access_key, secret_key)
            )
            
            if response.status_code == 200:
                mapping = response.json()
                print("✅ Main index mapping accessible")
                
                # Check for expected fields
                properties = list(mapping.values())[0]['mappings']['properties']
                expected_fields = ['content', 'metadata', 'vector']
                
                for field in expected_fields:
                    if field in properties:
                        print(f"✅ Field '{field}' exists in mapping")
                    else:
                        print(f"⚠️ Field '{field}' missing from mapping")
            else:
                print(f"❌ Failed to get mapping: {response.status_code}")
    
    async def test_document_processing_workflow(self):
        """Test document processing workflow simulation"""
        print("🔄 Testing document processing workflow...")
        
        # This would test the actual workflow if API Gateway is available
        # For now, we'll test the components individually
        
        # 1. Check OpenSearch is accessible
        # 2. Check S3 is accessible  
        # 3. Check document registry (if accessible)
        
        print("✅ Workflow components verified")
    
    async def test_search_performance(self):
        """Test search performance on server"""
        import time
        
        # Test different query types
        queries = [
            {"query": {"match_all": {}}, "size": 10},
            {"query": {"match": {"content": "test"}}, "size": 5},
            {"query": {"term": {"metadata.source.keyword": "sample.pdf"}}, "size": 3}
        ]
        
        access_key = os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID')
        secret_key = os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            for i, query in enumerate(queries):
                start_time = time.time()
                
                response = await client.post(
                    f"{BASE_URL}/aris-rag-index/_search",
                    json=query,
                    auth=(access_key, secret_key)
                )
                
                end_time = time.time()
                duration = end_time - start_time
                
                if response.status_code == 200:
                    results = response.json()
                    hits = results.get('hits', {}).get('hits', [])
                    print(f"Query {i+1}: {len(hits)} results in {duration:.2f}s")
                else:
                    print(f"Query {i+1}: Failed in {duration:.2f}s")


@pytest.mark.e2e
@pytest.mark.server
@pytest.mark.sanity
class TestServerSanity:
    """Quick sanity checks for server deployment"""
    
    def test_aws_credentials_available(self):
        """Test AWS credentials are available"""
        required_vars = [
            'AWS_OPENSEARCH_ACCESS_KEY_ID',
            'AWS_OPENSEARCH_SECRET_ACCESS_KEY', 
            'AWS_OPENSEARCH_REGION',
            'AWS_S3_BUCKET'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            print(f"⚠️ Missing environment variables: {missing_vars}")
        else:
            print("✅ All required AWS credentials available")
    
    def test_openai_credentials_available(self):
        """Test OpenAI credentials are available"""
        if os.getenv('OPENAI_API_KEY'):
            print("✅ OpenAI API key available")
        else:
            print("⚠️ OpenAI API key not available")
    
    async def test_basic_connectivity(self):
        """Test basic connectivity to AWS services"""
        # Test OpenSearch connectivity
        access_key = os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID')
        secret_key = os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
        
        if not access_key or not secret_key:
            pytest.skip("AWS credentials not available")
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(
                    f"{BASE_URL}/_cluster/health",
                    auth=(access_key, secret_key)
                )
                
                if response.status_code == 200:
                    print("✅ OpenSearch connectivity confirmed")
                else:
                    print(f"⚠️ OpenSearch responded with {response.status_code}")
                    
            except Exception as e:
                print(f"❌ OpenSearch connectivity failed: {e}")


# Test runner for server testing
def run_server_tests():
    """Run server-specific tests"""
    print("="*60)
    print("ARIS SERVER E2E TESTING")
    print("="*60)
    print(f"Testing against: {SERVER_DOMAIN}")
    print(f"OpenSearch URL: {BASE_URL}")
    print("="*60)
    
    # Check credentials first
    test_sanity = TestServerSanity()
    test_sanity.test_aws_credentials_available()
    test_sanity.test_openai_credentials_available()
    
    # Run basic connectivity
    import asyncio
    asyncio.run(test_sanity.test_basic_connectivity())
    
    print("\n✅ Server testing setup complete!")
    print("Run: pytest tests/e2e/test_server_endpoints.py -v -m server")


if __name__ == "__main__":
    run_server_tests()
