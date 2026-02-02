import os
import logging
from opensearchpy import OpenSearch, AWSV4SignerAuth
import boto3
from dotenv import load_dotenv

load_dotenv()

def inspect_opensearch_pages(index_name, search_term):
    host = 'search-intelycx-waseem-os-4e6bsxzyull4zxtvxul5keh4wu.us-east-2.es.amazonaws.com'
    region = 'us-east-2'
    
    # Manually load credentials from environment variables
    access_key = os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
    
    if not access_key or not secret_key:
        print("Error: AWS credentials not found in environment variables.")
        return

    from requests_aws4auth import AWS4Auth
    from opensearchpy import RequestsHttpConnection
    
    awsauth = AWS4Auth(
        access_key,
        secret_key,
        region,
        'es'
    )
    
    client = OpenSearch(
        hosts=[{'host': host, 'port': 443}],
        http_auth=awsauth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection
    )

    
    query = {
        "query": {
            "match": {
                "text": search_term
            }
        }
    }
    
    res = client.search(index=index_name, body=query)
    print(f"\nResults for '{search_term}' in index '{index_name}':")
    for hit in res['hits']['hits']:
        meta = hit['_source']['metadata']
        print(f"Page in Metadata: {meta.get('page')}")
        print(f"Extraction Method: {meta.get('page_extraction_method')}")
        print(f"Text Snippet: {hit['_source']['text'][:150]}...")
        print("-" * 50)

if __name__ == "__main__":
    # Question: "How to enable manual mode in VUORMAR?"
    # AI Page: 3, Physical Page: 2
    inspect_opensearch_pages("vuormar", "manual mode")

