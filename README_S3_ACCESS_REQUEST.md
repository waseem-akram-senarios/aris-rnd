# S3 Access Request Script

## Overview

The `test_s3_access_request.py` script tests S3 access with your current AWS credentials and generates a detailed error report that you can send to your AWS administrator to request S3 permissions.

## Usage

```bash
python3 test_s3_access_request.py
```

## What It Does

1. **Reads your OpenSearch credentials** from `.env` file
2. **Tests S3 access** using those credentials
3. **Generates detailed error report** if access is denied
4. **Creates a report file** (`S3_ACCESS_REQUEST_REPORT.txt`) that you can send to your AWS admin

## Output

The script will:

- ✅ **If S3 access works**: Shows success message
- ❌ **If S3 access is denied**: 
  - Displays detailed error information
  - Shows IAM user details (ARN, username, account ID)
  - Lists required permissions
  - Provides recommended IAM policy JSON
  - Saves everything to `S3_ACCESS_REQUEST_REPORT.txt`

## Report File Contents

The generated report includes:

1. **Error Details**
   - Error code and message
   - IAM user ARN
   - AWS account ID
   - IAM username

2. **Permission Request**
   - Clear request for S3 access
   - List of required permissions
   - Recommended IAM policy (JSON format)
   - Alternative options (managed policies)

3. **Full Error Message**
   - Complete error text for troubleshooting

## What to Send to AWS Administrator

Send the `S3_ACCESS_REQUEST_REPORT.txt` file along with:

1. **Request**: Grant S3 access to IAM user `WaseemOS`
2. **Account ID**: `975049910508`
3. **Required Permissions**: Listed in the report
4. **Policy**: Use the recommended IAM policy from the report

## After Permissions Are Granted

Run the script again to verify:

```bash
python3 test_s3_access_request.py
```

If successful, you'll see:
```
✅ SUCCESS: S3 access is working!
```

## Alternative: Separate IAM User

If your AWS admin prefers to keep OpenSearch and S3 credentials separate:

1. Request a new IAM user (e.g., `aris-s3-user`)
2. Attach S3 permissions to the new user
3. Get access key and secret key
4. Add to `.env` file:
   ```env
   AWS_ACCESS_KEY_ID=<new_user_access_key>
   AWS_SECRET_ACCESS_KEY=<new_user_secret_key>
   AWS_REGION=us-east-2
   ```

## Files Generated

- `S3_ACCESS_REQUEST_REPORT.txt` - Report file to send to AWS admin
