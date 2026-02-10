"""
Synchronous E2E tests for ARIS server deployment
Tests against the actual AWS server without async complications
"""
import pytest
import requests
import os
import json
from requests_aws4auth import AWS4Auth


# Server configuration
SERVER_DOMAIN = "search-intelycx-waseem-os-4e6bsxzyull4zxtvxul5keh4wu.us-east-2.es.amazonaws.com"
BASE_URL = f"https://{SERVER_DOMAIN}"


@pytest.mark.e2e
@pytest.mark.server
class TestServerConnectivity:
    """Test server connectivity with synchronous requests"""
    
    @pytest.fixture
    def aws_auth(self):
        """Create AWS4Auth for OpenSearch"""
        access_key = os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID')
        secret_key = os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
        region = os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')
        
        return AWS4Auth(access_key, secret_key, region, 'es')
    
    def test_opensearch_health(self, aws_auth):
        """Test OpenSearch cluster health"""
        response = requests.get(f"{BASE_URL}/_cluster/health", auth=aws_auth, timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        health = response.json()
        assert "status" in health
        assert "number_of_nodes" in health
        
        print(f"✅ Cluster Status: {health['status']}")
        print(f"   Nodes: {health['number_of_nodes']}")
        print(f"   Data Nodes: {health['number_of_data_nodes']}")
    
    def test_opensearch_indices(self, aws_auth):
        """Test OpenSearch indices"""
        response = requests.get(f"{BASE_URL}/_cat/indices?format=json", auth=aws_auth, timeout=30)
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        indices = response.json()
        assert len(indices) > 0, "No indices found"
        
        # Check for ARIS indices
        aris_indices = [idx for idx in indices if 'aris-rag' in idx['index']]
        assert len(aris_indices) > 0, "No ARIS indices found"
        
        print(f"✅ Found {len(indices)} total indices")
        print(f"✅ Found {len(aris_indices)} ARIS indices")
        
        # Show ARIS indices
        for idx in aris_indices:
            name = idx['index']
            docs = idx['docs.count'] if idx['docs.count'] != 'null' else '0'
            size = idx['store.size']
            print(f"   - {name}: {docs} docs, {size}")
    
    def test_document_search(self, aws_auth):
        """Test document search functionality"""
        # Search for documents
        search_query = {
            "query": {"match_all": {}},
            "size": 5
        }
        
        response = requests.post(
            f"{BASE_URL}/aris-rag-index/_search",
            json=search_query,
            auth=aws_auth,
            timeout=30
        )
        
        # Allow 404 if index doesn't exist yet
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}"
        
        if response.status_code == 200:
            results = response.json()
            hits = results.get('hits', {}).get('hits', [])
            print(f"✅ Document search successful: {len(hits)} documents found")
            
            if hits:
                doc = hits[0]['_source']
                assert 'content' in doc
                assert 'metadata' in doc
                
                metadata = doc.get('metadata', {})
                source = metadata.get('source', 'Unknown')
                page = metadata.get('page', 'N/A')
                print(f"   Sample document: {source} (Page {page})")
        else:
            print("ℹ️ No aris-rag-index found - documents may not be indexed yet")
    
    def test_image_search(self, aws_auth):
        """Test image search functionality"""
        search_query = {
            "query": {"match_all": {}},
            "size": 5
        }
        
        response = requests.post(
            f"{BASE_URL}/aris-rag-images-index/_search",
            json=search_query,
            auth=aws_auth,
            timeout=30
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        results = response.json()
        hits = results.get('hits', {}).get('hits', [])
        print(f"✅ Image search successful: {len(hits)} images found")
        
        if hits:
            doc = hits[0]['_source']
            # Check for either ocr_text, content, or text field
            content_fields = ['ocr_text', 'content', 'text']
            has_content = any(field in doc for field in content_fields)
            assert has_content, f"Image document missing content fields: {list(doc.keys())}"
            
            # Get the first available content field
            content = next((doc.get(field) for field in content_fields if doc.get(field)), 'No content')
            print(f"   Sample content: {content[:100]}...")
            
            # Check metadata
            metadata = doc.get('metadata', {})
            if metadata:
                source = metadata.get('source', 'Unknown')
                page = metadata.get('page', 'N/A')
                print(f"   Source: {source} (Page {page})")
        else:
            print("ℹ️ No images found")
    
    def test_search_with_query(self, aws_auth):
        """Test search with actual query"""
        # Search for specific terms
        search_query = {
            "query": {
                "match": {
                    "content": "test document"
                }
            },
            "size": 3
        }
        
        response = requests.post(
            f"{BASE_URL}/aris-rag-index/_search",
            json=search_query,
            auth=aws_auth,
            timeout=30
        )
        
        # Allow 404 if index doesn't exist
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}"
        
        if response.status_code == 200:
            results = response.json()
            hits = results.get('hits', {}).get('hits', [])
            print(f"✅ Query search successful: {len(hits)} results")
            
            if hits:
                for i, hit in enumerate(hits[:3]):
                    score = hit.get('_score', 0)
                    doc = hit['_source']
                    content = doc.get('content', '')[:100]
                    print(f"   Result {i+1}: Score {score:.2f} - {content}...")
    
    def test_index_mapping(self, aws_auth):
        """Test index mapping structure"""
        response = requests.get(
            f"{BASE_URL}/aris-rag-index/_mapping",
            auth=aws_auth,
            timeout=30
        )
        
        # Allow 404 if index doesn't exist
        assert response.status_code in [200, 404], f"Expected 200 or 404, got {response.status_code}"
        
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
            print("ℹ️ No aris-rag-index mapping found")


@pytest.mark.e2e
@pytest.mark.server
@pytest.mark.performance
class TestServerPerformance:
    """Test server performance"""
    
    @pytest.fixture
    def aws_auth(self):
        """Create AWS4Auth for OpenSearch"""
        access_key = os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID')
        secret_key = os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
        region = os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')
        
        return AWS4Auth(access_key, secret_key, region, 'es')
    
    def test_search_response_time(self, aws_auth):
        """Test search response times"""
        import time
        
        queries = [
            {"query": {"match_all": {}}, "size": 10},
            {"query": {"match": {"content": "document"}}, "size": 5},
            {"query": {"term": {"metadata.source.keyword": "test"}}, "size": 3}
        ]
        
        for i, query in enumerate(queries):
            start_time = time.time()
            
            response = requests.post(
                f"{BASE_URL}/aris-rag-index/_search",
                json=query,
                auth=aws_auth,
                timeout=30
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            # Allow 404 for missing index
            assert response.status_code in [200, 404], f"Query {i+1} failed: {response.status_code}"
            
            if response.status_code == 200:
                results = response.json()
                hits = results.get('hits', {}).get('hits', [])
                print(f"✅ Query {i+1}: {len(hits)} results in {duration:.2f}s")
                
                # Performance check
                assert duration < 5.0, f"Query {i+1} took too long: {duration:.2f}s"
            else:
                print(f"ℹ️ Query {i+1}: Index not found ({duration:.2f}s)")


@pytest.mark.e2e
@pytest.mark.server
@pytest.mark.sanity
class TestServerSanityChecks:
    """Quick sanity checks for server"""
    
    def test_credentials_available(self):
        """Test that required credentials are available"""
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
        
        assert len(missing_vars) == 0, f"Missing credentials: {missing_vars}"
        print("✅ All required credentials available")
    
    def test_openai_credentials_available(self):
        """Test OpenAI credentials"""
        assert os.getenv('OPENAI_API_KEY'), "OpenAI API key not available"
        print("✅ OpenAI API key available")
    
    def test_server_domain_reachable(self):
        """Test that server domain is reachable"""
        import socket
        
        try:
            # Test DNS resolution
            host = SERVER_DOMAIN.replace('https://', '').replace('http://', '')
            socket.gethostbyname(host)
            print(f"✅ Server domain {host} is reachable")
        except socket.gaierror:
            pytest.fail(f"Server domain {SERVER_DOMAIN} is not reachable")


if __name__ == "__main__":
    # Run tests directly
    pytest.main([__file__, "-v", "-m", "server"])
