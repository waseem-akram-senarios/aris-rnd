import os, requests, json, sys
from requests.auth import HTTPBasicAuth

output_file = "/tmp/audit_output.txt"

with open(output_file, "w") as search_out:
    print("Starting audit...", file=search_out)
    
    try:
        u = os.environ.get('OPENSEARCH_USERNAME', 'admin')
        p = os.environ.get('OPENSEARCH_PASSWORD', 'admin')
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
        
        print(f"Requesting {url}...", file=search_out)
        
        # Try Basic Auth
        resp = requests.post(url, auth=HTTPBasicAuth(u, p), json=q, verify=False)
        
        if resp.status_code != 200:
            print(f"Basic Auth Error: {resp.status_code} - {resp.text[:200]}", file=search_out)
            # Try AWS4Auth
            try:
                from requests_aws4auth import AWS4Auth
                au = os.environ.get('AWS_OPENSEARCH_ACCESS_KEY_ID')
                ap = os.environ.get('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
                ar = os.environ.get('AWS_OPENSEARCH_REGION', 'us-east-2')
                if au and ap:
                    print("Trying AWS4Auth...", file=search_out)
                    auth = AWS4Auth(au, ap, ar, 'es')
                    resp = requests.post(url, auth=auth, json=q, verify=False)
            except Exception as e:
                print(f"AWS4Auth exception: {e}", file=search_out)

        if resp.status_code == 200:
            data = resp.json()
            hits = data.get('hits', {}).get('hits', [])
            print(f"Found {len(hits)} images.", file=search_out)
            print(f"{'IMG_NUM':<8} | {'PAGE':<5} | {'OCR_LEN':<8} | {'ID'}", file=search_out)
            print("-" * 60, file=search_out)
            
            for h in hits:
                s = h['_source']
                m = s.get('metadata', {})
                img_num = m.get('image_number')
                page = m.get('page')
                ocr_text = s.get('ocr_text') or s.get('text') or ""
                _id = h['_id']
                print(f"{str(img_num):<8} | {str(page):<5} | {len(ocr_text):<8} | {_id}", file=search_out)
        else:
            print(f"Final Error: {resp.status_code} - {resp.text[:500]}", file=search_out)

    except Exception as e:
        print(f"EXCEPTION: {str(e)}", file=search_out)
        import traceback
        traceback.print_exc(file=search_out)

print(f"Audit completed. Output written to {output_file}")
