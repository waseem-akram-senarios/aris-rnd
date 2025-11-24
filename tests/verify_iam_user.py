#!/usr/bin/env python3
"""
Verify IAM User Details
Checks your actual IAM username and ARN from AWS.
"""
import os
import boto3
from dotenv import load_dotenv
from botocore.exceptions import ClientError

load_dotenv('.env')

# Get credentials
access_key = os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID')
secret_key = os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
region = os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')

print("=" * 70)
print("IAM User Verification")
print("=" * 70)
print()

if not access_key or not secret_key:
    print("❌ Error: AWS credentials not found in .env file")
    sys.exit(1)

try:
    # Method 1: Use STS to get caller identity
    print("Method 1: Using STS (Security Token Service)")
    print("-" * 70)
    
    sts_client = boto3.client(
        'sts',
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region
    )
    
    try:
        identity = sts_client.get_caller_identity()
        
        print("✅ Successfully retrieved identity")
        print()
        print("Your IAM Details:")
        print(f"   User ID: {identity.get('UserId', 'N/A')}")
        print(f"   Account: {identity.get('Account', 'N/A')}")
        print(f"   ARN: {identity.get('Arn', 'N/A')}")
        print()
        
        # Extract username from ARN
        arn = identity.get('Arn', '')
        if 'user/' in arn:
            username = arn.split('user/')[-1]
            print(f"   Username: {username}")
        elif 'assumed-role' in arn:
            role_name = arn.split('assumed-role/')[-1].split('/')[0]
            print(f"   Role: {role_name}")
            print("   ⚠️  You're using an assumed role, not a direct IAM user")
        else:
            print("   ⚠️  Could not extract username from ARN")
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'AccessDenied':
            print("❌ Access denied - Cannot get caller identity")
            print("   This might mean your credentials don't have STS permissions")
        else:
            print(f"❌ Error: {error_code}")
            print(f"   {e.response['Error']['Message']}")
    
    print()
    
    # Method 2: Try IAM directly (if we have permissions)
    print("Method 2: Using IAM Service (if permissions allow)")
    print("-" * 70)
    
    try:
        iam_client = boto3.client(
            'iam',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
        
        # Try to get current user
        try:
            user_info = iam_client.get_user()
            user = user_info.get('User', {})
            
            print("✅ Successfully retrieved user info")
            print()
            print("Your IAM User Details:")
            print(f"   Username: {user.get('UserName', 'N/A')}")
            print(f"   User ID: {user.get('UserId', 'N/A')}")
            print(f"   ARN: {user.get('Arn', 'N/A')}")
            print(f"   Created: {user.get('CreateDate', 'N/A')}")
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'AccessDenied':
                print("❌ Access denied - Cannot get user info")
                print("   Your credentials don't have IAM get_user permissions")
            elif error_code == 'NoSuchEntity':
                print("⚠️  User not found - You might be using a role, not a user")
            else:
                print(f"❌ Error: {error_code}")
                print(f"   {e.response['Error']['Message']}")
    
    except Exception as e:
        print(f"⚠️  Could not access IAM service: {str(e)[:100]}")
    
    print()
    
    # Method 3: Check from OpenSearch domain access
    print("Method 3: From OpenSearch Domain Access")
    print("-" * 70)
    
    try:
        opensearch_client = boto3.client(
            'opensearch',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        
        # Get domain info to see who has access
        domain_info = opensearch_client.describe_domain(DomainName='intelycx-os-dev')
        domain_status = domain_info.get('DomainStatus', {})
        
        print("✅ Can access OpenSearch domain")
        print(f"   Domain: intelycx-os-dev")
        print(f"   Status: Active")
        print()
        print("   Note: Your IAM user has access to this domain")
        print("   (but needs OpenSearch role permissions for operations)")
        
    except Exception as e:
        print(f"⚠️  Could not access OpenSearch: {str(e)[:100]}")
    
    print()
    print("=" * 70)
    print("Summary")
    print("=" * 70)
    print()
    print("Use the ARN from Method 1 (STS) for your permission request.")
    print("The ARN format is: arn:aws:iam::ACCOUNT:user/USERNAME")
    print()
    print("If you see 'assumed-role' in the ARN, you're using a role.")
    print("In that case, you may need to provide the role ARN instead.")
    print()

except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()

