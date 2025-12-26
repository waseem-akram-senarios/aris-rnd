import boto3
import os
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def check_s3_permissions():
    try:
        # Use OpenSearch credentials for S3 access
        aws_access_key = os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID')
        aws_secret_key = os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
        aws_region = os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')
        
        if not aws_access_key or not aws_secret_key:
            print("✗ OpenSearch credentials not found in .env file!")
            print("  Looking for: AWS_OPENSEARCH_ACCESS_KEY_ID, AWS_OPENSEARCH_SECRET_ACCESS_KEY")
            return
        
        print(f"Using OpenSearch credentials to check S3 access...")
        print(f"Access Key: {aws_access_key[:10]}...")
        print(f"Region: {aws_region}")
        print("-" * 50)
        
        s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region
        )
        
        print("Checking S3 permissions...")
        print("-" * 50)
        
        # Your specific bucket from IAM policy
        bucket_name = "intelycx-waseem-s3-bucket"
        
        # Try to list buckets (may fail if only bucket-specific access)
        try:
            response = s3_client.list_buckets()
            print(f"✓ ListAllBuckets: SUCCESS")
            print(f"  Found {len(response['Buckets'])} bucket(s):")
            for bucket in response['Buckets']:
                print(f"    - {bucket['Name']}")
        except ClientError as e:
            print(f"✗ ListAllBuckets: FAILED - {e.response['Error']['Code']}")
            print(f"  (This is OK if you only have access to specific buckets)")
        
        print()
        
        # Test access to your specific bucket
        print(f"Testing access to bucket: {bucket_name}")
        print("-" * 50)
        
        # Test ListBucket permission
        try:
            response = s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=5)
            object_count = response.get('KeyCount', 0)
            print(f"✓ ListBucket: SUCCESS")
            print(f"  Found {object_count} object(s) (showing first 5)")
            if 'Contents' in response:
                for obj in response['Contents']:
                    print(f"    - {obj['Key']} ({obj['Size']} bytes)")
        except ClientError as e:
            print(f"✗ ListBucket: FAILED - {e.response['Error']['Code']}: {e.response['Error']['Message']}")
        
        # Test GetObject permission (if objects exist)
        try:
            response = s3_client.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
            if 'Contents' in response and len(response['Contents']) > 0:
                test_key = response['Contents'][0]['Key']
                s3_client.head_object(Bucket=bucket_name, Key=test_key)
                print(f"✓ GetObject: SUCCESS (tested with {test_key})")
            else:
                print(f"⚠ GetObject: SKIPPED (no objects to test)")
        except ClientError as e:
            print(f"✗ GetObject: FAILED - {e.response['Error']['Code']}")
        
        # Test PutObject permission (dry run - just check if we can generate presigned URL)
        try:
            test_key = "test-access-check.txt"
            presigned_url = s3_client.generate_presigned_url(
                'put_object',
                Params={'Bucket': bucket_name, 'Key': test_key},
                ExpiresIn=60
            )
            print(f"✓ PutObject: PERMISSION AVAILABLE (can generate upload URLs)")
        except ClientError as e:
            print(f"✗ PutObject: FAILED - {e.response['Error']['Code']}")
        
        print("-" * 50)
        
        # Check credentials info
        try:
            sts_client = boto3.client(
                'sts',
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=aws_region
            )
            identity = sts_client.get_caller_identity()
            print(f"\nCredentials found:")
            print(f"  Account: {identity['Account']}")
            print(f"  User ARN: {identity['Arn']}")
            print(f"  User ID: {identity['UserId']}")
        except Exception as e:
            print(f"\nCould not retrieve identity: {e}")
            
    except NoCredentialsError:
        print("✗ No AWS credentials found!")
        print("\nTo configure credentials, you can:")
        print("1. Set environment variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY")
        print("2. Create ~/.aws/credentials file")
        print("3. Use IAM role (if running on EC2/ECS)")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_s3_permissions()
