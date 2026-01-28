import os, requests, json, sys
from requests.auth import HTTPBasicAuth

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)

print("Starting mapping check...")

try:
    u = os.environ.get('OPENSEARCH_USERNAME', 'admin')
    p = os.environ.get('OPENSEARCH_PASSWORD', 'admin')
    d = 'search-intelycx-waseem-os-4e6bsxzyull4zxtvxul5keh4wu.us-east-2.es.amazonaws.com'
    url = f'https://{d}/aris-rag-images-index/_mapping'
    
    print(f"Requesting {url}...")
    
    # Try Basic Auth
    resp = requests.get(url, auth=HTTPBasicAuth(u, p), verify=False)
    
    if resp.status_code != 200:
        print(f"Basic Auth failed: {resp.status_code}")
        # Try AWS4Auth
        try:
            from requests_aws4auth import AWS4Auth
            au = os.environ.get('AWS_OPENSEARCH_ACCESS_KEY_ID')
            ap = os.environ.get('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
            ar = os.environ.get('AWS_OPENSEARCH_REGION', 'us-east-2')
            if au and ap:
                print("Trying AWS4Auth...")
                auth = AWS4Auth(au, ap, ar, 'es')
                resp = requests.get(url, auth=auth, verify=False)
        except Exception as e:
            print(f"AWS4Auth setup failed: {e}")

    if resp.status_code == 200:
        print("Success! Mapping:")
        # Print only metadata properties to save space
        data = resp.json()
        props = data.get('aris-rag-images-index', {}).get('mappings', {}).get('properties', {})
        meta_props = props.get('metadata', {}).get('properties', {})
        print(json.dumps(meta_props, indent=2))
        
        # Check image_number specifically
        if 'image_number' in meta_props:
            print(f"FOUND image_number: {meta_props['image_number']}")
        else:
            print("WARNING: image_number NOT FOUND in metadata properties")
    else:
        print(f"Failed to get mapping: {resp.status_code} - {resp.text}")

except Exception as e:
    print(f"EXCEPTION: {e}")
