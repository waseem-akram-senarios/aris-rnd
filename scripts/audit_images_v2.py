import os, requests, json, sys
from requests.auth import HTTPBasicAuth
# Use HTTPBasicAuth first as it is more standard for the admin user
# If that fails, we can try AWS4Auth but usually admin/admin works with HTTPBasicAuth on these setups

print("Starting audit...", file=sys.stderr)

try:
    u = os.environ.get('OPENSEARCH_USERNAME', 'admin')
    p = os.environ.get('OPENSEARCH_PASSWORD', 'admin')
    # Try different env vars if defaults fail
    if u == 'admin' and os.environ.get('AWS_OPENSEARCH_ACCESS_KEY_ID'):
         print("Note: AWS env vars present but using basic auth admin/admin first", file=sys.stderr)

    d = 'search-intelycx-waseem-os-4e6bsxzyull4zxtvxul5keh4wu.us-east-2.es.amazonaws.com'
    url = f'https://{d}/aris-rag-images-index/_search'
    
    q = {
        "size": 100,
        "query": {
            "match_phrase": {
                "metadata.source": "EM11, top seal(spa).pdf"
            }
        },
        "sort": [
            {"metadata.image_number": {"order": "asc"}}
        ]
    }
    
    print(f"Requesting {url}...", file=sys.stderr)
    # Verify=False to skip SSL cert check which is common issue
    resp = requests.post(url, auth=HTTPBasicAuth(u, p), json=q, verify=False)
    
    if resp.status_code != 200:
        print(f"Error: {resp.status_code} - {resp.text}", file=sys.stderr)
        # Try AWS4Auth as fallback
        try:
            from requests_aws4auth import AWS4Auth
            print("Basic auth failed, trying AWS4Auth...", file=sys.stderr)
            au = os.environ.get('AWS_OPENSEARCH_ACCESS_KEY_ID')
            ap = os.environ.get('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
            ar = os.environ.get('AWS_OPENSEARCH_REGION', 'us-east-2')
            if au and ap:
                auth = AWS4Auth(au, ap, ar, 'es')
                resp = requests.post(url, auth=auth, json=q, verify=False)
        except Exception as e:
            print(f"AWS4Auth failed: {e}", file=sys.stderr)

    if resp.status_code != 200:
        print("All auth methods failed.", file=sys.stderr)
        sys.exit(1)

    data = resp.json()
    hits = data.get('hits', {}).get('hits', [])
    
    print(f"Found {len(hits)} images.")
    print(f"{'IMG_NUM':<8} | {'PAGE':<5} | {'OCR_LEN':<8} | {'ID'}")
    print("-" * 60)
    
    for h in hits:
        s = h['_source']
        m = s.get('metadata', {})
        img_num = m.get('image_number')
        page = m.get('page')
        ocr_text = s.get('ocr_text') or s.get('text') or ""
        _id = h['_id']
        print(f"{str(img_num):<8} | {str(page):<5} | {len(ocr_text):<8} | {_id}")

except Exception as e:
    print(f"EXCEPTION: {str(e)}", file=sys.stderr)
