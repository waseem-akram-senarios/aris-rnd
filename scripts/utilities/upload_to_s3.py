import boto3
import os
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

def upload_file_to_s3():
    # Get credentials from .env
    aws_access_key = os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID')
    aws_secret_key = os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
    aws_region = os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')
    
    # S3 configuration
    bucket_name = "intelycx-waseem-s3-bucket"
    local_file = "test_upload.txt"
    s3_key = f"test-uploads/test_upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    
    print("=" * 60)
    print("S3 Upload Test")
    print("=" * 60)
    print(f"Bucket: {bucket_name}")
    print(f"Local file: {local_file}")
    print(f"S3 key: {s3_key}")
    print(f"Region: {aws_region}")
    print("-" * 60)
    
    try:
        # Create S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region
        )
        
        # Check if file exists
        if not os.path.exists(local_file):
            print(f"✗ Error: Local file '{local_file}' not found!")
            return False
        
        file_size = os.path.getsize(local_file)
        print(f"File size: {file_size} bytes")
        print()
        
        # Upload file
        print("Uploading file to S3...")
        with open(local_file, 'rb') as file_data:
            s3_client.put_object(
                Bucket=bucket_name,
                Key=s3_key,
                Body=file_data,
                ContentType='text/plain',
                Metadata={
                    'uploaded-by': 'WaseemOS',
                    'upload-date': datetime.now().isoformat(),
                    'source': 'ARIS-RAG-System'
                }
            )
        
        print("✅ Upload successful!")
        print()
        print("Upload Details:")
        print(f"  ✓ Bucket: {bucket_name}")
        print(f"  ✓ S3 Key: {s3_key}")
        print(f"  ✓ Size: {file_size} bytes")
        print(f"  ✓ Region: {aws_region}")
        print()
        print(f"S3 URI: s3://{bucket_name}/{s3_key}")
        print(f"S3 URL: https://{bucket_name}.s3.{aws_region}.amazonaws.com/{s3_key}")
        print()
        print("⚠️  Note: You cannot verify this upload by listing or downloading")
        print("   because ListBucket and GetObject permissions are blocked.")
        print("   However, the upload operation completed without errors!")
        print("=" * 60)
        
        return True
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        print(f"✗ Upload failed!")
        print(f"  Error Code: {error_code}")
        print(f"  Error Message: {error_message}")
        print("=" * 60)
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = upload_file_to_s3()
    exit(0 if success else 1)
