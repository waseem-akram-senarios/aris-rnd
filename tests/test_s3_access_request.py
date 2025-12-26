#!/usr/bin/env python3
"""
S3 Access Test Script - Generates error report for AWS administrator
Use this to request S3 access permissions from your AWS admin.
"""
import os
import sys
import json
from datetime import datetime

def read_opensearch_credentials():
    """Read OpenSearch credentials from .env file."""
    env_file = '.env'
    opensearch_key = None
    opensearch_secret = None
    opensearch_region = 'us-east-2'
    
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('AWS_OPENSEARCH_ACCESS_KEY_ID='):
                    opensearch_key = line.split('=', 1)[1].strip()
                elif line.startswith('AWS_OPENSEARCH_SECRET_ACCESS_KEY='):
                    opensearch_secret = line.split('=', 1)[1].strip()
                elif line.startswith('AWS_OPENSEARCH_REGION='):
                    opensearch_region = line.split('=', 1)[1].strip()
    
    return opensearch_key, opensearch_secret, opensearch_region

def test_s3_access():
    """Test S3 access and generate detailed error report."""
    print("="*80)
    print("S3 ACCESS TEST - For AWS Administrator Request")
    print("="*80)
    print()
    
    # Read credentials
    opensearch_key, opensearch_secret, opensearch_region = read_opensearch_credentials()
    
    if not opensearch_key or not opensearch_secret:
        print("❌ ERROR: OpenSearch credentials not found in .env file")
        print("   Please ensure AWS_OPENSEARCH_ACCESS_KEY_ID and")
        print("   AWS_OPENSEARCH_SECRET_ACCESS_KEY are set in .env file")
        return None
    
    print("📋 Testing S3 Access with Current Credentials:")
    print(f"   IAM User: (will be identified from error message)")
    print(f"   Region: {opensearch_region}")
    print(f"   Access Key ID: {opensearch_key[:10]}...{opensearch_key[-4:]}")
    print()
    
    # Test S3 access
    try:
        import boto3
    except ImportError:
        print("❌ ERROR: boto3 is not installed")
        print("   Install it with: pip install boto3")
        return None
    
    try:
        # Create S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=opensearch_key,
            aws_secret_access_key=opensearch_secret,
            region_name=opensearch_region
        )
        
        print("🔍 Attempting to list S3 buckets...")
        print()
        
        # Try to list buckets
        try:
            response = s3_client.list_buckets()
            buckets = response.get('Buckets', [])
            
            print("✅ SUCCESS: S3 access is working!")
            print(f"   Found {len(buckets)} bucket(s)")
            return {
                'status': 'success',
                'buckets': len(buckets),
                'message': 'S3 access is already available'
            }
            
        except Exception as e:
            # Extract error details
            error_msg = str(e)
            error_code = getattr(e, 'response', {}).get('Error', {}).get('Code', 'Unknown')
            error_message = getattr(e, 'response', {}).get('Error', {}).get('Message', error_msg)
            
            # Extract IAM user ARN from error message
            iam_user_arn = None
            if 'arn:aws:iam::' in error_msg:
                import re
                match = re.search(r'arn:aws:iam::\d+:user/\w+', error_msg)
                if match:
                    iam_user_arn = match.group(0)
            
            # Extract account ID
            account_id = None
            if iam_user_arn:
                match = re.search(r'arn:aws:iam::(\d+):', iam_user_arn)
                if match:
                    account_id = match.group(1)
            
            # Extract IAM username
            iam_username = None
            if iam_user_arn:
                iam_username = iam_user_arn.split('/')[-1]
            
            print("❌ S3 ACCESS DENIED")
            print()
            print("="*80)
            print("ERROR DETAILS FOR AWS ADMINISTRATOR")
            print("="*80)
            print()
            print(f"Error Code: {error_code}")
            print(f"Error Message: {error_message}")
            print()
            
            if iam_user_arn:
                print(f"IAM User ARN: {iam_user_arn}")
                print(f"AWS Account ID: {account_id}")
                print(f"IAM Username: {iam_username}")
                print()
            
            print("="*80)
            print("PERMISSION REQUEST FOR AWS ADMINISTRATOR")
            print("="*80)
            print()
            print("REQUEST:")
            print("--------")
            print(f"Please grant S3 access permissions to IAM user: {iam_username}")
            print(f"Account ID: {account_id}")
            print(f"IAM User ARN: {iam_user_arn}")
            print()
            print("REQUIRED PERMISSIONS:")
            print("---------------------")
            print("The following S3 permissions are required:")
            print()
            print("1. s3:ListAllMyBuckets")
            print("   - Allows listing all S3 buckets in the account")
            print()
            print("2. s3:CreateBucket")
            print("   - Allows creating new S3 buckets")
            print("   - Resource: arn:aws:s3:::bucket-name")
            print()
            print("3. s3:ListBucket")
            print("   - Allows listing objects in a bucket")
            print("   - Resource: arn:aws:s3:::bucket-name")
            print()
            print("4. s3:GetObject")
            print("   - Allows reading/downloading objects from buckets")
            print("   - Resource: arn:aws:s3:::bucket-name/*")
            print()
            print("5. s3:PutObject")
            print("   - Allows uploading objects to buckets")
            print("   - Resource: arn:aws:s3:::bucket-name/*")
            print()
            print("6. s3:DeleteObject")
            print("   - Allows deleting objects from buckets")
            print("   - Resource: arn:aws:s3:::bucket-name/*")
            print()
            print("7. s3:DeleteBucket (Optional)")
            print("   - Allows deleting buckets")
            print("   - Resource: arn:aws:s3:::bucket-name")
            print()
            print("RECOMMENDED IAM POLICY:")
            print("----------------------")
            print("Attach the following policy to the IAM user:")
            print()
            
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:ListAllMyBuckets"
                        ],
                        "Resource": "*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:CreateBucket",
                            "s3:ListBucket",
                            "s3:GetBucketLocation",
                            "s3:DeleteBucket"
                        ],
                        "Resource": "arn:aws:s3:::*"
                    },
                    {
                        "Effect": "Allow",
                        "Action": [
                            "s3:GetObject",
                            "s3:PutObject",
                            "s3:DeleteObject"
                        ],
                        "Resource": "arn:aws:s3:::*/*"
                    }
                ]
            }
            
            print(json.dumps(policy, indent=2))
            print()
            print("OR use AWS managed policy:")
            print("   - AmazonS3FullAccess (for full access)")
            print("   - AmazonS3ReadOnlyAccess (for read-only access)")
            print()
            print("="*80)
            print("ALTERNATIVE: CREATE SEPARATE IAM USER FOR S3")
            print("="*80)
            print()
            print("If you prefer to keep OpenSearch and S3 credentials separate:")
            print()
            print("1. Create a new IAM user (e.g., 'aris-s3-user')")
            print("2. Attach S3 permissions to the new user")
            print("3. Provide access key and secret key for the new user")
            print("4. Add to .env file as:")
            print("   AWS_ACCESS_KEY_ID=<new_user_access_key>")
            print("   AWS_SECRET_ACCESS_KEY=<new_user_secret_key>")
            print("   AWS_REGION=us-east-2")
            print()
            print("="*80)
            print("TEST INFORMATION")
            print("="*80)
            print()
            print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Test Command: python3 test_s3_access_request.py")
            print(f"Error Code: {error_code}")
            print(f"Full Error: {error_msg}")
            print()
            print("="*80)
            
            # Save report to file
            report_file = 'S3_ACCESS_REQUEST_REPORT.txt'
            with open(report_file, 'w') as f:
                f.write("="*80 + "\n")
                f.write("S3 ACCESS REQUEST REPORT\n")
                f.write("="*80 + "\n")
                f.write(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("\n" + "="*80 + "\n")
                f.write("ERROR DETAILS\n")
                f.write("="*80 + "\n\n")
                f.write(f"Error Code: {error_code}\n")
                f.write(f"Error Message: {error_message}\n\n")
                if iam_user_arn:
                    f.write(f"IAM User ARN: {iam_user_arn}\n")
                    f.write(f"AWS Account ID: {account_id}\n")
                    f.write(f"IAM Username: {iam_username}\n\n")
                f.write("\n" + "="*80 + "\n")
                f.write("PERMISSION REQUEST\n")
                f.write("="*80 + "\n\n")
                f.write(f"Please grant S3 access permissions to IAM user: {iam_username}\n")
                f.write(f"Account ID: {account_id}\n")
                f.write(f"IAM User ARN: {iam_user_arn}\n\n")
                f.write("REQUIRED PERMISSIONS:\n")
                f.write("---------------------\n")
                f.write("1. s3:ListAllMyBuckets\n")
                f.write("2. s3:CreateBucket\n")
                f.write("3. s3:ListBucket\n")
                f.write("4. s3:GetObject\n")
                f.write("5. s3:PutObject\n")
                f.write("6. s3:DeleteObject\n")
                f.write("7. s3:DeleteBucket (Optional)\n\n")
                f.write("RECOMMENDED IAM POLICY:\n")
                f.write("----------------------\n")
                f.write(json.dumps(policy, indent=2))
                f.write("\n\n")
                f.write("="*80 + "\n")
                f.write("FULL ERROR MESSAGE\n")
                f.write("="*80 + "\n\n")
                f.write(error_msg)
                f.write("\n")
            
            print(f"✅ Report saved to: {report_file}")
            print("   You can send this file to your AWS administrator")
            print()
            
            return {
                'status': 'denied',
                'error_code': error_code,
                'error_message': error_message,
                'iam_user_arn': iam_user_arn,
                'iam_username': iam_username,
                'account_id': account_id,
                'report_file': report_file
            }
            
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = test_s3_access()
    
    if result and result.get('status') == 'success':
        print("\n✅ S3 access is already working - no action needed!")
        sys.exit(0)
    elif result and result.get('status') == 'denied':
        print("\n📧 Next Steps:")
        print("   1. Review the error details above")
        print("   2. Send the report file to your AWS administrator")
        print("   3. Request S3 permissions as specified")
        print("   4. After permissions are granted, run this script again to verify")
        sys.exit(1)
    else:
        print("\n❌ Test failed - check error messages above")
        sys.exit(1)

