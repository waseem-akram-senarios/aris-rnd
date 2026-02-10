import os
import requests
from requests.auth import HTTPBasicAuth
import json

# OpenSearch credentials
u = os.environ.get('OPENSEARCH_USERNAME')
p = os.environ.get('OPENSEARCH_PASSWORD')
d = 'search-intelycx-waseem-os-4e6bsxzyull4zxtvxul5keh4wu.us-east-2.es.amazonaws.com'
idx = 'aris-rag-images'

url = f'https://{d}/{idx}/_search'
# Search for 'calentamiento' in the images index
q = {
    'query': {
        'match': {'ocr_text': 'calentamiento'}
    },
    'size': 10
}

r = requests.post(url, auth=HTTPBasicAuth(u, p), json=q, verify=False)
data = r.json()
hits = data.get('hits', {}).get('hits', [])
print(f"FOUND {len(hits)} HITS")
for h in hits:
    s = h['_source']
    print(f"ID: {h['_id']}")
    print(f"PAGE: {s.get('page')}")
    print(f"SRC: {s.get('source')}")
    print(f"OCR: {s.get('ocr_text', '')[:300]}")
    print("-" * 20)
