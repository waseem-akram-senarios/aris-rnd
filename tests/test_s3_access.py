#!/usr/bin/env python3
"""
Test script to check S3 bucket access and upload capability
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()

def test_s3_access():
    """Test if S3 access is available and list buckets"""
    try:
        import boto3
    except ImportError:
        print("❌ boto3 is not installed")
        print("   Install it with: pip install boto3")
        return False
    
    # Get AWS credentials
    aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_REGION', os.getenv('AWS_DEFAULT_REGION', 'us-east-1'))
    
    if not aws_access_key or not aws_secret_key:
        print("❌ AWS credentials not found in environment variables")
        print("   Required: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY")
        print("   Optional: AWS_REGION (default: us-east-1)")
        return False
    
    print(f"✅ AWS credentials found")
    print(f"   Region: {aws_region}")
    
    try:
        # Create S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region
        )
        
        # List buckets
        print("\n📦 Testing S3 access...")
        response = s3_client.list_buckets()
        
        buckets = response.get('Buckets', [])
        print(f"✅ S3 access successful!")
        print(f"   Found {len(buckets)} bucket(s):")
        
        for bucket in buckets:
            bucket_name = bucket['Name']
            creation_date = bucket['CreationDate']
            print(f"   - {bucket_name} (created: {creation_date})")
        
        # Test upload permission (try to list objects in first bucket)
        if buckets:
            test_bucket = buckets[0]['Name']
            print(f"\n🔍 Testing read access to bucket: {test_bucket}")
            try:
                objects = s3_client.list_objects_v2(Bucket=test_bucket, MaxKeys=5)
                print(f"✅ Read access confirmed")
                if 'Contents' in objects:
                    print(f"   Found {len(objects['Contents'])} object(s) (showing first 5)")
                else:
                    print("   Bucket is empty")
            except Exception as e:
                print(f"⚠️  Read access test failed: {e}")
            
            # Test upload permission (try to upload a small test file)
            print(f"\n📤 Testing upload permission to bucket: {test_bucket}")
            test_key = "test_upload_access.txt"
            test_content = b"Test file for S3 upload access check"
            try:
                s3_client.put_object(
                    Bucket=test_bucket,
                    Key=test_key,
                    Body=test_content
                )
                print(f"✅ Upload permission confirmed!")
                print(f"   Successfully uploaded test file: {test_key}")
                
                # Clean up - delete test file
                try:
                    s3_client.delete_object(Bucket=test_bucket, Key=test_key)
                    print(f"   Cleaned up test file")
                except Exception as e:
                    print(f"⚠️  Could not delete test file: {e}")
                    
            except Exception as e:
                error_code = getattr(e, 'response', {}).get('Error', {}).get('Code', 'Unknown')
                print(f"❌ Upload permission denied: {error_code}")
                print(f"   Error: {e}")
                return False
        
        return True
        
    except Exception as e:
        error_code = getattr(e, 'response', {}).get('Error', {}).get('Code', 'Unknown')
        print(f"❌ S3 access failed: {error_code}")
        print(f"   Error: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("S3 Access Test")
    print("=" * 60)
    success = test_s3_access()
    print("\n" + "=" * 60)
    if success:
        print("✅ S3 access is available and working!")
    else:
        print("❌ S3 access is not available or not configured")
    print("=" * 60)
    sys.exit(0 if success else 1)

