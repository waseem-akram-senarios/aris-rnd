import os, requests, json, sys
from requests.auth import HTTPBasicAuth, AWS4Auth

print("Verifying fix for Page 6 image hallucination...")

try:
    u = os.environ.get('OPENSEARCH_USERNAME', 'admin')
    p = os.environ.get('OPENSEARCH_PASSWORD', 'admin')
    d = 'search-intelycx-waseem-os-4e6bsxzyull4zxtvxul5keh4wu.us-east-2.es.amazonaws.com'
    url = f'https://{d}/aris-rag-images-index/_search'
    
    # Query that previously returned the text chunk as an image
    # Note: We are simulating what the CODE does (adding the filter)
    # Since I cannot update the server code live and expect it to be running instantly without redeploy,
    # I must verify if the FILTER I added *would* work against the current data.
    # So I will construct the query WITH the filter I just added to the codebase.
    
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
    
    # Also verify the BAD query (without filter) returns the bad doc
    q_bad = {
        "size": 5,
        "query": {
            "bool": {
                "must": [
                    # NO content_type filter
                    {"match_phrase": {"metadata.source": "EM11, top seal(spa).pdf"}}
                ]
            }
        }
    }
    
    # Helper to run query
    def run_q(query_body, label):
        print(f"\nRunning {label}...")
        try:
            resp = requests.post(url, auth=HTTPBasicAuth(u, p), json=query_body, verify=False)
            if resp.status_code != 200:
                # Try AWS4Auth
                au = os.environ.get('AWS_OPENSEARCH_ACCESS_KEY_ID')
                ap = os.environ.get('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
                ar = os.environ.get('AWS_OPENSEARCH_REGION', 'us-east-2')
                auth = AWS4Auth(au, ap, ar, 'es')
                resp = requests.post(url, auth=auth, json=query_body, verify=False)
            
            if resp.status_code == 200:
                hits = resp.json().get('hits', {}).get('hits', [])
                print(f"Found {len(hits)} hits.")
                for h in hits:
                    m = h['_source'].get('metadata', {})
                    ct = m.get('content_type', 'UNKNOWN')
                    page = m.get('page')
                    print(f" - Page: {page}, Type: {ct}, ID: {h['_id']}")
                return hits
            else:
                print(f"Error: {resp.status_code} {resp.text}")
                return []
        except Exception as e:
            print(f"Exception: {e}")
            return []

    # 1. Run BAD query (baseline)
    bad_hits = run_q(q_bad, "BASELINE (No Filter)")
    
    # 2. Run GOOD query (With Fix)
    good_hits = run_q(q, "VERIFICATION (With content_type Filter)")
    
    # Analyze
    bad_count = len([h for h in bad_hits if h['_source'].get('metadata', {}).get('content_type') == 'text'])
    good_count = len([h for h in good_hits if h['_source'].get('metadata', {}).get('content_type') == 'text'])
    
    print("\n--- RESULTS ---")
    print(f"Polluted 'text' chunks in BASELINE: {bad_count}")
    print(f"Polluted 'text' chunks in VERIFICATION: {good_count}")
    
    if bad_count > 0 and good_count == 0:
        print("✅ SUCCESS: The filter successfully removes polluted text chunks!")
    elif bad_count == 0:
        print("⚠️ WARNING: Baseline didn't find polluted chunks. Filter might not be needed or query is wrong.")
        # Try finding ANY text chunk
        print("Searching for ANY 'text' content_type...")
        q_any_text = {
            "size": 1,
            "query": {"term": {"metadata.content_type.keyword": "text"}}
        }
        run_q(q_any_text, "ANY text chunk")
    else:
        print(f"❌ FAILURE: Filter did not remove polluted chunks (Count: {good_count})")

except Exception as e:
    print(f"Script Error: {e}")
