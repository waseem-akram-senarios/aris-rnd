#!/usr/bin/env python3
"""
Comprehensive AWS Permissions Checker
Tests all AWS service permissions for the current IAM user
"""
import boto3
import os
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def get_aws_credentials():
    """Get AWS credentials from environment"""
    access_key = os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID') or os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY') or os.getenv('AWS_SECRET_ACCESS_KEY')
    region = os.getenv('AWS_OPENSEARCH_REGION') or os.getenv('AWS_REGION') or 'us-east-2'
    return access_key, secret_key, region

def check_sts_permissions(region):
    """Check STS (Security Token Service) permissions"""
    print("\n" + "="*70)
    print("1. STS (Security Token Service) Permissions")
    print("="*70)
    
    try:
        sts = boto3.client('sts', region_name=region)
        identity = sts.get_caller_identity()
        
        print("✅ GetCallerIdentity: SUCCESS")
        print(f"   Account: {identity.get('Account')}")
        print(f"   User ARN: {identity.get('Arn')}")
        print(f"   User ID: {identity.get('UserId')}")
        return True
    except Exception as e:
        print(f"❌ GetCallerIdentity: FAILED - {str(e)}")
        return False

def check_s3_permissions(region, bucket_name='intelycx-waseem-s3-bucket'):
    """Check S3 permissions"""
    print("\n" + "="*70)
    print("2. S3 (Simple Storage Service) Permissions")
    print("="*70)
    print(f"Bucket: {bucket_name}")
    
    results = {}
    s3 = boto3.client('s3', region_name=region)
    
    # Test ListAllMyBuckets
    try:
        response = s3.list_buckets()
        print("✅ ListAllMyBuckets: SUCCESS")
        print(f"   Found {len(response.get('Buckets', []))} bucket(s)")
        results['ListAllMyBuckets'] = True
    except ClientError as e:
        error_code = e.response['Error']['Code']
        print(f"❌ ListAllMyBuckets: {error_code}")
        results['ListAllMyBuckets'] = False
    
    # Test ListBucket
    try:
        response = s3.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
        print("✅ ListBucket: SUCCESS")
        results['ListBucket'] = True
    except ClientError as e:
        error_code = e.response['Error']['Code']
        print(f"❌ ListBucket: {error_code}")
        results['ListBucket'] = False
    
    # Test PutObject
    test_key = f"permission-test/{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    try:
        s3.put_object(
            Bucket=bucket_name,
            Key=test_key,
            Body=b"Test upload for permission check",
            ContentType='text/plain'
        )
        print(f"✅ PutObject: SUCCESS (uploaded {test_key})")
        results['PutObject'] = True
        
        # Test GetObject
        try:
            response = s3.get_object(Bucket=bucket_name, Key=test_key)
            data = response['Body'].read()
            print(f"✅ GetObject: SUCCESS (retrieved {len(data)} bytes)")
            results['GetObject'] = True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            print(f"❌ GetObject: {error_code}")
            results['GetObject'] = False
        
        # Test DeleteObject
        try:
            s3.delete_object(Bucket=bucket_name, Key=test_key)
            print(f"✅ DeleteObject: SUCCESS (deleted {test_key})")
            results['DeleteObject'] = True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            print(f"❌ DeleteObject: {error_code}")
            results['DeleteObject'] = False
            
    except ClientError as e:
        error_code = e.response['Error']['Code']
        print(f"❌ PutObject: {error_code}")
        results['PutObject'] = False
    
    return results

def check_opensearch_permissions(region, domain='intelycx-waseem-os'):
    """Check OpenSearch permissions"""
    print("\n" + "="*70)
    print("3. OpenSearch Permissions")
    print("="*70)
    print(f"Domain: {domain}")
    
    results = {}
    
    try:
        es = boto3.client('es', region_name=region)
        
        # Test DescribeElasticsearchDomain
        try:
            response = es.describe_elasticsearch_domain(DomainName=domain)
            print("✅ DescribeElasticsearchDomain: SUCCESS")
            print(f"   Domain Status: {response['DomainStatus'].get('Processing', 'Unknown')}")
            results['DescribeElasticsearchDomain'] = True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            print(f"❌ DescribeElasticsearchDomain: {error_code}")
            results['DescribeElasticsearchDomain'] = False
        
        # Test ListDomainNames
        try:
            response = es.list_domain_names()
            print("✅ ListDomainNames: SUCCESS")
            print(f"   Found {len(response.get('DomainNames', []))} domain(s)")
            results['ListDomainNames'] = True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            print(f"❌ ListDomainNames: {error_code}")
            results['ListDomainNames'] = False
            
    except Exception as e:
        print(f"❌ OpenSearch Client Error: {str(e)}")
        results['Error'] = str(e)
    
    return results

def check_textract_permissions(region):
    """Check Textract permissions"""
    print("\n" + "="*70)
    print("4. Textract (OCR) Permissions")
    print("="*70)
    
    results = {}
    
    try:
        textract = boto3.client('textract', region_name=region)
        
        # Test DetectDocumentText (synchronous)
        # Note: This requires a document, so we'll just check if the client can be created
        print("✅ Textract Client: Created successfully")
        print("   (Full Textract operations require document upload)")
        results['TextractClient'] = True
        
        # Try to get account attributes (if available)
        try:
            # Textract doesn't have a simple "list" API, but we can check permissions
            # by attempting a simple operation
            print("   Note: Textract operations require document input")
            results['DetectDocumentText'] = 'Requires document'
        except Exception as e:
            print(f"   Info: {str(e)}")
            
    except Exception as e:
        print(f"❌ Textract Client Error: {str(e)}")
        results['Error'] = str(e)
    
    return results

def check_iam_permissions(region):
    """Check IAM permissions"""
    print("\n" + "="*70)
    print("5. IAM (Identity and Access Management) Permissions")
    print("="*70)
    
    results = {}
    
    try:
        iam = boto3.client('iam', region_name=region)
        
        # Test GetUser
        try:
            response = iam.get_user()
            print("✅ GetUser: SUCCESS")
            print(f"   User: {response['User'].get('UserName')}")
            results['GetUser'] = True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            print(f"❌ GetUser: {error_code}")
            results['GetUser'] = False
        
        # Test ListAttachedUserPolicies
        try:
            response = iam.list_attached_user_policies(UserName=response['User']['UserName'])
            print("✅ ListAttachedUserPolicies: SUCCESS")
            print(f"   Attached Policies: {len(response.get('AttachedPolicies', []))}")
            results['ListAttachedUserPolicies'] = True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            print(f"❌ ListAttachedUserPolicies: {error_code}")
            results['ListAttachedUserPolicies'] = False
        
        # Test ListUserPolicies (inline policies)
        try:
            user_name = iam.get_user()['User']['UserName']
            response = iam.list_user_policies(UserName=user_name)
            print("✅ ListUserPolicies: SUCCESS")
            print(f"   Inline Policies: {len(response.get('PolicyNames', []))}")
            results['ListUserPolicies'] = True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            print(f"❌ ListUserPolicies: {error_code}")
            results['ListUserPolicies'] = False
            
    except Exception as e:
        print(f"❌ IAM Client Error: {str(e)}")
        results['Error'] = str(e)
    
    return results

def check_ec2_permissions(region):
    """Check EC2 permissions"""
    print("\n" + "="*70)
    print("6. EC2 Permissions")
    print("="*70)
    
    results = {}
    
    try:
        ec2 = boto3.client('ec2', region_name=region)
        
        # Test DescribeInstances
        try:
            response = ec2.describe_instances()
            instance_count = sum(len(reservation.get('Instances', [])) for reservation in response.get('Reservations', []))
            print("✅ DescribeInstances: SUCCESS")
            print(f"   Found {instance_count} instance(s)")
            results['DescribeInstances'] = True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            print(f"❌ DescribeInstances: {error_code}")
            results['DescribeInstances'] = False
        
        # Test DescribeRegions
        try:
            response = ec2.describe_regions()
            print("✅ DescribeRegions: SUCCESS")
            print(f"   Available Regions: {len(response.get('Regions', []))}")
            results['DescribeRegions'] = True
        except ClientError as e:
            error_code = e.response['Error']['Code']
            print(f"❌ DescribeRegions: {error_code}")
            results['DescribeRegions'] = False
            
    except Exception as e:
        print(f"❌ EC2 Client Error: {str(e)}")
        results['Error'] = str(e)
    
    return results

def main():
    """Main function to check all permissions"""
    print("="*70)
    print("COMPREHENSIVE AWS PERMISSIONS CHECK")
    print("="*70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    access_key, secret_key, region = get_aws_credentials()
    
    if not access_key or not secret_key:
        print("\n❌ ERROR: No AWS credentials found!")
        print("   Please set AWS_OPENSEARCH_ACCESS_KEY_ID and AWS_OPENSEARCH_SECRET_ACCESS_KEY")
        return 1
    
    print(f"\nRegion: {region}")
    print(f"Access Key: {access_key[:10]}...")
    
    # Set credentials in environment for boto3
    os.environ['AWS_ACCESS_KEY_ID'] = access_key
    os.environ['AWS_SECRET_ACCESS_KEY'] = secret_key
    
    all_results = {}
    
    # Check all services
    all_results['STS'] = check_sts_permissions(region)
    all_results['S3'] = check_s3_permissions(region)
    all_results['OpenSearch'] = check_opensearch_permissions(region)
    all_results['Textract'] = check_textract_permissions(region)
    all_results['IAM'] = check_iam_permissions(region)
    all_results['EC2'] = check_ec2_permissions(region)
    
    # Summary
    print("\n" + "="*70)
    print("PERMISSION SUMMARY")
    print("="*70)
    
    for service, results in all_results.items():
        if isinstance(results, dict):
            success_count = sum(1 for v in results.values() if v is True)
            total_count = sum(1 for v in results.values() if isinstance(v, bool))
            print(f"\n{service}:")
            if total_count > 0:
                print(f"   ✅ {success_count}/{total_count} permissions granted")
            for perm, status in results.items():
                if isinstance(status, bool):
                    icon = "✅" if status else "❌"
                    print(f"   {icon} {perm}")
        elif isinstance(results, bool):
            icon = "✅" if results else "❌"
            print(f"{service}: {icon}")
    
    print("\n" + "="*70)
    print("Check complete!")
    print("="*70)
    
    return 0

if __name__ == "__main__":
    exit(main())




