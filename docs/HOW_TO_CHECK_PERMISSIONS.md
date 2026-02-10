# How to Verify Your OpenSearch Permissions

## Quick Method: Run the Permission Checker Script

I've created a script that automatically checks all your permissions:

```bash
cd /home/senarios/Desktop/aris
source venv/bin/activate
python3 check_opensearch_permissions.py
```

This script will:
- ✅ Test AWS API permissions (list/describe domains)
- ✅ Test OpenSearch cluster permissions
- ✅ Test index admin permissions
- ✅ Test data write permissions
- ✅ Test data read permissions
- 📊 Show a summary of what you have and what you don't have

## What the Script Checks

### 1. AWS API Permissions
- `list_domain_names` - Can you see available domains?
- `describe_domain` - Can you get domain information?

### 2. OpenSearch Cluster Permissions
- `cluster:monitor/main` - Can you get basic cluster info?
- `cluster:monitor/health` - Can you check cluster health?

### 3. Index Admin Permissions
- `indices:admin/get` - Can you list indices?
- `indices:admin/create` - Can you create new indices?

### 4. Data Write Permissions
- `indices:data/write/index` - Can you write documents?

### 5. Data Read Permissions
- `indices:data/read/search` - Can you search documents?

## Understanding the Output

### ✅ Green Checkmarks
- Means you HAVE that permission
- You can perform that operation

### ❌ Red X Marks
- Means you DON'T HAVE that permission
- You cannot perform that operation
- You need to request this permission

### ⚠️ Yellow Warnings
- Connection or authentication issues
- May indicate missing permissions

## Example Output

```
✅ Permissions You HAVE (2):
   • AWS API: describe_domain
   • AWS API: list_domain_names

❌ Permissions You DON'T HAVE (5):
   • OpenSearch: cluster:monitor/main
   • OpenSearch: indices:admin/create
   • OpenSearch: indices:admin/get
   • OpenSearch: indices:data/read/search
   • OpenSearch: indices:data/write/index
```

## Manual Testing (Alternative Method)

If you want to test manually, you can use Python:

```python
from opensearchpy import OpenSearch
from requests_aws4auth import AWS4Auth
import os
from dotenv import load_dotenv

load_dotenv()

# Setup
access_key = os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID')
secret_key = os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
endpoint = "https://search-intelycx-os-dev-avu6r2aoemtqc3gaojwzvmaj4u.us-east-2.es.amazonaws.com"

# Connect
awsauth = AWS4Auth(access_key, secret_key, 'us-east-2', 'es')
client = OpenSearch(hosts=[endpoint], http_auth=awsauth, use_ssl=True)

# Test permissions
try:
    # Test 1: Cluster info
    info = client.info()
    print("✅ Can get cluster info")
except Exception as e:
    print(f"❌ Cannot get cluster info: {e}")

try:
    # Test 2: List indices
    indices = client.cat.indices(format='json')
    print("✅ Can list indices")
except Exception as e:
    print(f"❌ Cannot list indices: {e}")

try:
    # Test 3: Create index
    client.indices.create(index='test-index', body={"settings": {"number_of_shards": 1}})
    print("✅ Can create indices")
    client.indices.delete(index='test-index')
except Exception as e:
    print(f"❌ Cannot create indices: {e}")

try:
    # Test 4: Write document
    client.index(index='test-index', body={"test": "data"})
    print("✅ Can write documents")
except Exception as e:
    print(f"❌ Cannot write documents: {e}")

try:
    # Test 5: Search
    result = client.search(index='test-index', body={"query": {"match_all": {}}})
    print("✅ Can search documents")
except Exception as e:
    print(f"❌ Cannot search documents: {e}")
```

## Common Permission Errors

### Error: `no permissions for [cluster:monitor/main]`
- **Meaning:** You don't have basic cluster access
- **Impact:** Cannot authenticate or perform any operations
- **Fix:** Request `cluster:monitor/main` permission first

### Error: `no permissions for [indices:admin/get]`
- **Meaning:** Cannot list or get index information
- **Impact:** Cannot see what indices exist
- **Fix:** Request `indices:admin/get` permission

### Error: `no permissions for [indices:admin/create]`
- **Meaning:** Cannot create new indices
- **Impact:** Cannot create indices for RAG system
- **Fix:** Request `indices:admin/create` permission

### Error: `no permissions for [indices:data/write/index]`
- **Meaning:** Cannot write documents
- **Impact:** Cannot add documents to indices
- **Fix:** Request `indices:data/write/index` permission

### Error: `no permissions for [indices:data/read/search]`
- **Meaning:** Cannot search documents
- **Impact:** Cannot query the RAG system
- **Fix:** Request `indices:data/read/search` permission

## After Getting Permissions

1. **Run the checker again:**
   ```bash
   python3 check_opensearch_permissions.py
   ```

2. **Verify all permissions show ✅**

3. **Test the RAG system:**
   ```bash
   python3 test_vector_stores_e2e.py
   ```

## Quick Reference

| Permission | What It Allows | Required for RAG? |
|------------|----------------|-------------------|
| `cluster:monitor/main` | Basic cluster access | ✅ Yes (authentication) |
| `indices:admin/create` | Create indices | ✅ Yes (create index) |
| `indices:admin/get` | List/get indices | ✅ Yes (check index exists) |
| `indices:data/write/index` | Write documents | ✅ Yes (add documents) |
| `indices:data/read/search` | Search documents | ✅ Yes (query RAG) |

## Need Help?

If you see errors you don't understand:
1. Copy the full error message
2. Check the error message for the permission name (e.g., `no permissions for [permission_name]`)
3. Request that specific permission from your OpenSearch administrator

