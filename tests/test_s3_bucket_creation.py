#!/usr/bin/env python3
"""
Test S3 Bucket Creation Permissions
Checks if you can create S3 buckets with current credentials
"""
import os
import sys
import boto3
from datetime import datetime

def read_credentials():
    """Read AWS credentials from .env file."""
    env_file = '.env'
    aws_key = None
    aws_secret = None
    aws_region = 'us-east-2'
    
    # Try OpenSearch credentials first
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('AWS_OPENSEARCH_ACCESS_KEY_ID='):
                    aws_key = line.split('=', 1)[1].strip()
                elif line.startswith('AWS_OPENSEARCH_SECRET_ACCESS_KEY='):
                    aws_secret = line.split('=', 1)[1].strip()
                elif line.startswith('AWS_OPENSEARCH_REGION='):
                    aws_region = line.split('=', 1)[1].strip()
                # Also check for general AWS credentials
                elif line.startswith('AWS_ACCESS_KEY_ID=') and not aws_key:
                    aws_key = line.split('=', 1)[1].strip()
                elif line.startswith('AWS_SECRET_ACCESS_KEY=') and not aws_secret:
                    aws_secret = line.split('=', 1)[1].strip()
                elif line.startswith('AWS_REGION=') and aws_region == 'us-east-2':
                    aws_region = line.split('=', 1)[1].strip()
    
    return aws_key, aws_secret, aws_region

def test_bucket_creation():
    """Test if we can create an S3 bucket."""
    print("="*80)
    print("S3 BUCKET CREATION TEST")
    print("="*80)
    
    # Read credentials
    aws_key, aws_secret, aws_region = read_credentials()
    
    if not aws_key or not aws_secret:
        print("\n❌ ERROR: AWS credentials not found in .env file")
        print("   Please ensure credentials are set")
        return False
    
    print(f"\n📋 Using Credentials:")
    print(f"   Region: {aws_region}")
    print(f"   Access Key: {aws_key[:10]}...{aws_key[-4:]}")
    
    try:
        # Create S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_key,
            aws_secret_access_key=aws_secret,
            region_name=aws_region
        )
        
        # Generate unique test bucket name
        test_bucket_name = f"aris-test-bucket-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        print(f"\n🔍 Testing bucket creation...")
        print(f"   Test bucket name: {test_bucket_name}")
        print(f"   Region: {aws_region}")
        
        try:
            # Try to create bucket
            print("\n   Attempting to create bucket...")
            
            # For us-east-1, don't use LocationConstraint
            if aws_region == 'us-east-1':
                s3_client.create_bucket(Bucket=test_bucket_name)
            else:
                s3_client.create_bucket(
                    Bucket=test_bucket_name,
                    CreateBucketConfiguration={
                        'LocationConstraint': aws_region
                    }
                )
            
            print(f"\n✅ SUCCESS: Bucket created!")
            print(f"   Bucket name: {test_bucket_name}")
            print(f"   Region: {aws_region}")
            
            # Clean up - delete the test bucket
            print("\n   Cleaning up test bucket...")
            try:
                # First, make sure bucket is empty
                objects = s3_client.list_objects_v2(Bucket=test_bucket_name)
                if 'Contents' in objects:
                    for obj in objects['Contents']:
                        s3_client.delete_object(Bucket=test_bucket_name, Key=obj['Key'])
                
                s3_client.delete_bucket(Bucket=test_bucket_name)
                print("   ✅ Test bucket deleted successfully")
            except Exception as e:
                print(f"   ⚠️  Could not delete test bucket: {e}")
                print(f"   Please manually delete: {test_bucket_name}")
            
            print("\n" + "="*80)
            print("✅ CONCLUSION: You CAN create S3 buckets!")
            print("="*80)
            return True
            
        except Exception as e:
            error_msg = str(e)
            error_code = getattr(e, 'response', {}).get('Error', {}).get('Code', 'Unknown')
            error_message = getattr(e, 'response', {}).get('Error', {}).get('Message', error_msg)
            
            print(f"\n❌ BUCKET CREATION FAILED")
            print(f"   Error Code: {error_code}")
            print(f"   Error: {error_message[:300]}")
            
            if 'AccessDenied' in error_code or 'AccessDenied' in error_msg:
                print("\n   💡 You do NOT have permission to create S3 buckets")
                print("   💡 Required permission: s3:CreateBucket")
            elif 'BucketAlreadyExists' in error_code or 'BucketAlreadyOwnedByYou' in error_code:
                print("\n   ⚠️  Bucket name already exists")
                print("   💡 This actually means you HAVE permissions (name collision)")
                return True
            elif 'InvalidBucketName' in error_code:
                print("\n   💡 Invalid bucket name format")
            elif 'InvalidAccessKeyId' in error_code:
                print("\n   💡 Invalid credentials")
            else:
                print(f"\n   💡 Error type: {error_code}")
            
            print("\n" + "="*80)
            print("❌ CONCLUSION: You CANNOT create S3 buckets")
            print("="*80)
            print("\n📋 Required Permissions for Bucket Creation:")
            print("   - s3:CreateBucket")
            print("   - s3:PutBucketVersioning (optional)")
            print("   - s3:PutBucketPublicAccessBlock (optional)")
            print("\n💡 Add these to your S3 access request!")
            return False
            
    except ImportError:
        print("\n❌ ERROR: boto3 is not installed")
        print("   Install it with: pip install boto3")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_bucket_creation()
    sys.exit(0 if success else 1)

