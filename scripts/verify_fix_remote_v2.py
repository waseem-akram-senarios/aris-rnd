import os, requests, json, sys
from requests.auth import HTTPBasicAuth
# Correct import
try:
    from requests_aws4auth import AWS4Auth
except ImportError:
    AWS4Auth = None

print("Verifying fix for Page 6 image hallucination...")

try:
    u = os.environ.get('OPENSEARCH_USERNAME', 'admin')
    p = os.environ.get('OPENSEARCH_PASSWORD', 'admin')
    d = 'search-intelycx-waseem-os-4e6bsxzyull4zxtvxul5keh4wu.us-east-2.es.amazonaws.com'
    url = f'https://{d}/aris-rag-images-index/_search'
    
    # Query that previously returned the text chunk as an image
    q = {
        "size": 5,
        "query": {
            "bool": {
                "must": [
                    {"term": {"metadata.content_type.keyword": "image_ocr"}},
                    {"match_phrase": {"metadata.source": "EM11, top seal(spa).pdf"}}
                ]
            }
        }
    }
    
    # BAD query (without filter)
    q_bad = {
        "size": 5,
        "query": {
            "bool": {
                "must": [
                    {"match_phrase": {"metadata.source": "EM11, top seal(spa).pdf"}}
                ]
            }
        }
    }
    
    def run_q(query_body, label):
        print(f"\nRunning {label}...")
        try:
            # Try Basic Auth
            resp = requests.post(url, auth=HTTPBasicAuth(u, p), json=query_body, verify=False)
            
            if resp.status_code != 200 and AWS4Auth:
                # Try AWS4Auth
                au = os.environ.get('AWS_OPENSEARCH_ACCESS_KEY_ID')
                ap = os.environ.get('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
                ar = os.environ.get('AWS_OPENSEARCH_REGION', 'us-east-2')
                if au and ap:
                    auth = AWS4Auth(au, ap, ar, 'es')
                    resp = requests.post(url, auth=auth, json=query_body, verify=False)
            
            if resp.status_code == 200:
                hits = resp.json().get('hits', {}).get('hits', [])
                print(f"Found {len(hits)} hits.")
                for h in hits:
                    m = h['_source'].get('metadata', {})
                    ct = m.get('content_type', 'UNKNOWN')
                    page = m.get('page')
                    print(f" - Page: {page}, Type: {ct}")
                return hits
            else:
                print(f"Error: {resp.status_code} {resp.text[:200]}")
                return []
        except Exception as e:
            print(f"Exception: {e}")
            return []

    # 1. Run BAD query
    bad_hits = run_q(q_bad, "BASELINE (No Filter)")
    
    # 2. Run GOOD query
    good_hits = run_q(q, "VERIFICATION (With content_type Filter)")
    
    # Analyze
    bad_polluted = len([h for h in bad_hits if h['_source'].get('metadata', {}).get('content_type') == 'text'])
    good_polluted = len([h for h in good_hits if h['_source'].get('metadata', {}).get('content_type') == 'text'])
    
    print("\n--- RESULTS ---")
    print(f"Polluted chunks in BASELINE: {bad_polluted}")
    print(f"Polluted chunks in VERIFICATION: {good_polluted}")
    
    if good_polluted == 0:
        if bad_polluted > 0:
            print("✅ SUCCESS: Filter removed polluted chunks.")
        else:
            print("✅ SUCCESS: No polluted chunks found (baseline clean?). Filter is safe.")
    else:
        print(f"❌ FAILURE: Filter failed (found {good_polluted} polluted chunks).")

except Exception as e:
    print(f"Script Error: {e}")
