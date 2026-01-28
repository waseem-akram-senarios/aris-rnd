import os, requests, json, sys
from requests_aws4auth import AWS4Auth

output_file = "/tmp/mapping_output.txt"

with open(output_file, "w") as f:
    try:
        u = os.environ.get('AWS_OPENSEARCH_ACCESS_KEY_ID')
        p = os.environ.get('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
        r = os.environ.get('AWS_OPENSEARCH_REGION', 'us-east-2')
        d = 'search-intelycx-waseem-os-4e6bsxzyull4zxtvxul5keh4wu.us-east-2.es.amazonaws.com'
        
        auth = AWS4Auth(u, p, r, 'es')
        url = f'https://{d}/aris-rag-images-index/_mapping'
        
        print(f"Requesting {url}...", file=f)
        resp = requests.get(url, auth=auth, verify=False)
        
        print(f"Status: {resp.status_code}", file=f)
        if resp.status_code == 200:
            print(json.dumps(resp.json(), indent=2), file=f)
        else:
            print(resp.text, file=f)

    except Exception as e:
        print(f"EXCEPTION: {str(e)}", file=f)

print(f"Done. Output in {output_file}")
