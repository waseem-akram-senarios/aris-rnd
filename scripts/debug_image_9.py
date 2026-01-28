import os, requests, json
from requests_aws4auth import AWS4Auth
import boto3

def get_image_9():
    u = os.environ.get('AWS_OPENSEARCH_ACCESS_KEY_ID')
    p = os.environ.get('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
    r = os.environ.get('AWS_OPENSEARCH_REGION', 'us-east-2')
    d = 'search-intelycx-waseem-os-4e6bsxzyull4zxtvxul5keh4wu.us-east-2.es.amazonaws.com'
    
    auth = AWS4Auth(u, p, r, 'es')
    url = f'https://{d}/aris-rag-images-index/_search'
    
    # Just search for any document matching the source and image 9
    q = {
        "query": {
            "bool": {
                "must": [
                    {"match_phrase": {"metadata.source": "EM11, top seal(spa).pdf"}},
                    {"term": {"metadata.image_number": 9}}
                ]
            }
        }
    }
    
    try:
        resp = requests.post(url, auth=auth, json=q, verify=False)
        data = resp.json()
        hits = data.get('hits', {}).get('hits', [])
        if not hits:
            return "NO HITS"
        
        results = []
        for h in hits:
            s = h['_source']
            m = s.get('metadata', {})
            results.append({
                "id": h['_id'],
                "page": m.get('page'),
                "text_start": s.get('text', '')[:200],
                "text_end": s.get('text', '')[-200:],
                "metadata_keys": list(m.keys())
            })
        return json.dumps(results, indent=2)
    except Exception as e:
        return f"ERROR: {str(e)}"

if __name__ == "__main__":
    print(get_image_9())
