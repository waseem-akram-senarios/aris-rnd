import os, requests, json
from requests.auth import AWS4Auth
import boto3

def audit_images():
    u = os.environ.get('AWS_OPENSEARCH_ACCESS_KEY_ID')
    p = os.environ.get('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
    r = os.environ.get('AWS_OPENSEARCH_REGION', 'us-east-2')
    d = 'search-intelycx-waseem-os-4e6bsxzyull4zxtvxul5keh4wu.us-east-2.es.amazonaws.com'
    
    auth = AWS4Auth(u, p, r, 'es')
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
    
    try:
        print(f"Querying {url}...")
        resp = requests.post(url, auth=auth, json=q, verify=False)
        data = resp.json()
        hits = data.get('hits', {}).get('hits', [])
        
        print(f"Found {len(hits)} images.")
        print("IMG_NUM | PAGE | ID")
        print("-" * 30)
        
        for h in hits:
            s = h['_source']
            m = s.get('metadata', {})
            img_num = m.get('image_number')
            page = m.get('page')
            _id = h['_id']
            print(f"{img_num:<7} | {page:<4} | {_id}")
            
    except Exception as e:
        print(f"ERROR: {str(e)}")

if __name__ == "__main__":
    audit_images()
