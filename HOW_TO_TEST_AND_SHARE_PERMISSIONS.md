# How to Test and Share OpenSearch Permissions

## Quick Start

### 1. Run the Test Script
```bash
cd /home/senarios/Desktop/aris
source venv/bin/activate
python3 tests/test_opensearch_permissions_detailed.py
```

### 2. What You Get

The script will:
- ✅ Show which permissions you HAVE
- ❌ Show which permissions you DON'T HAVE
- ⚠️ Show any errors
- 📄 Generate a JSON report: `opensearch_permissions_report.json`

### 3. Share with Your Team

**Files to share:**
1. **Email:** `emails/RESPONSE_OPENSEARCH_INDEX_DETAILS_CONCISE.txt`
2. **JSON Report:** `opensearch_permissions_report.json`
3. **Test Script Output:** Copy the console output

## Files Created

### 📧 Concise Email
**File:** `emails/RESPONSE_OPENSEARCH_INDEX_DETAILS_CONCISE.txt`
- Short, clear explanation of what you need
- Index requirements and purpose
- Three options for proceeding
- Ready to send

### 🔧 Test Script
**File:** `tests/test_opensearch_permissions_detailed.py`
- Comprehensive permission testing
- Shows all errors with details
- Generates JSON report automatically
- Can be run anytime to check status

### 📄 JSON Report
**File:** `opensearch_permissions_report.json`
- Machine-readable format
- Contains all test results
- Includes error messages
- Can be shared with administrators

## What the Test Shows

### ✅ Permissions You HAVE
- AWS API: list_domain_names
- AWS API: describe_domain

### ❌ Permissions You DON'T HAVE
- OpenSearch: cluster:monitor/main (CRITICAL - blocks everything)
- OpenSearch: indices:admin/get
- OpenSearch: indices:admin/create
- OpenSearch: indices:data/write/index
- OpenSearch: indices:data/read/search

### 🔍 Key Finding
The error shows: `backend_roles=[]`
- IAM user is NOT mapped to any OpenSearch role
- Domain uses Fine-Grained Access Control (FGAC)
- Need OpenSearch-level role mapping

## Example Output

```
✅ Permissions You HAVE (2):
   • AWS API: describe_domain
   • AWS API: list_domain_names

❌ Permissions You DON'T HAVE (2):
   • OpenSearch: cluster:monitor/main
   • OpenSearch: indices:admin/get

📊 Test Summary:
   Total Tests: 4
   Passed: 2
   Failed: 2
   Errors: 0

⚠️  CRITICAL: Missing 'cluster:monitor/main' permission
   This blocks all other OpenSearch operations.
```

## Next Steps

1. **Run the test script** to get current status
2. **Review the concise email** and customize if needed
3. **Send email + JSON report** to your OpenSearch administrator
4. **Re-run test script** after permissions are granted to verify

## Re-testing After Permissions Granted

After your administrator grants permissions, run the script again:
```bash
python3 tests/test_opensearch_permissions_detailed.py
```

This will show if the new permissions are working.

