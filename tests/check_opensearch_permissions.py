#!/usr/bin/env python3
"""
OpenSearch Permissions Checker
Verifies which permissions you have and which you don't have.
"""
import os
import sys
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError

load_dotenv('.env')

# Configuration
access_key = os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID')
secret_key = os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
region = os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')
domain_name = 'intelycx-os-dev'
endpoint = "https://search-intelycx-os-dev-avu6r2aoemtqc3gaojwzvmaj4u.us-east-2.es.amazonaws.com"

print("=" * 70)
print("OpenSearch Permissions Verification Tool")
print("=" * 70)
print()
print(f"Domain: {domain_name}")
print(f"Endpoint: {endpoint}")
print(f"Region: {region}")
print()

if not access_key or not secret_key:
    print("❌ Error: OpenSearch credentials not found in .env file")
    sys.exit(1)

results = {
    'have': [],
    'dont_have': [],
    'errors': []
}

# Test 1: AWS API Permissions
print("=" * 70)
print("1. AWS API Permissions (via boto3)")
print("=" * 70)
print()

try:
    opensearch_client = boto3.client(
        'opensearch',
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region
    )
    
    # Test list_domain_names
    try:
        domains = opensearch_client.list_domain_names()
        print("✅ list_domain_names - CAN list domains")
        results['have'].append("AWS API: list_domain_names")
        if domains.get('DomainNames'):
            print(f"   Found {len(domains['DomainNames'])} domain(s)")
    except ClientError as e:
        if e.response['Error']['Code'] == 'AccessDenied':
            print("❌ list_domain_names - CANNOT list domains")
            results['dont_have'].append("AWS API: list_domain_names")
        else:
            print(f"⚠️  list_domain_names - Error: {e.response['Error']['Code']}")
            results['errors'].append(f"list_domain_names: {e.response['Error']['Code']}")
    
    # Test describe_domain
    try:
        domain_info = opensearch_client.describe_domain(DomainName=domain_name)
        print("✅ describe_domain - CAN describe domain")
        results['have'].append("AWS API: describe_domain")
        status = domain_info.get('DomainStatus', {})
        print(f"   Domain status: {status.get('Processing', 'Active')}")
    except ClientError as e:
        if e.response['Error']['Code'] == 'AccessDenied':
            print("❌ describe_domain - CANNOT describe domain")
            results['dont_have'].append("AWS API: describe_domain")
        else:
            print(f"⚠️  describe_domain - Error: {e.response['Error']['Code']}")
            results['errors'].append(f"describe_domain: {e.response['Error']['Code']}")
    
except Exception as e:
    print(f"❌ Error connecting to AWS: {str(e)}")
    results['errors'].append(f"AWS connection: {str(e)}")

print()

# Test 2: OpenSearch Direct API Permissions
print("=" * 70)
print("2. OpenSearch Direct API Permissions")
print("=" * 70)
print()

try:
    from opensearchpy import OpenSearch
    
    # Try different authentication methods
    auth_working = False
    client = None
    
    # Method 1: Try AWS4Auth
    try:
        from requests_aws4auth import AWS4Auth
        from opensearchpy import RequestsHttpConnection
        
        awsauth = AWS4Auth(access_key, secret_key, region, 'es')
        client = OpenSearch(
            hosts=[endpoint],
            http_auth=awsauth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            ssl_show_warn=False
        )
        # Test connection
        client.info()
        auth_working = True
        print("✅ Authentication: AWS4Auth working")
    except Exception as e:
        # Method 2: Try HTTP Basic Auth
        try:
            client = OpenSearch(
                hosts=[endpoint],
                http_auth=(access_key, secret_key),
                use_ssl=True,
                verify_certs=True,
                ssl_show_warn=False
            )
            client.info()
            auth_working = True
            print("✅ Authentication: HTTP Basic Auth working")
        except Exception as e2:
            print(f"❌ Authentication failed: {str(e)[:100]}")
            print("   Cannot test OpenSearch permissions without authentication")
            auth_working = False
    
    # Even if auth fails, try to extract permission info from errors
    if not auth_working:
        print("⚠️  Authentication issue detected")
        print("   This usually means missing cluster:monitor/main permission")
        results['dont_have'].append("OpenSearch: cluster:monitor/main")
        print("   Cannot test other permissions without basic cluster access")
        print()
        print("   This is the first permission you need to request!")
    
    if auth_working and client:
        # Test cluster permissions
        print("\n📊 Cluster Permissions:")
        print("-" * 70)
        
        # cluster:monitor/main
        try:
            info = client.info()
            print("✅ cluster:monitor/main - CAN get cluster info")
            results['have'].append("OpenSearch: cluster:monitor/main")
            print(f"   Cluster: {info.get('cluster_name', 'N/A')}")
        except Exception as e:
            error_msg = str(e)
            if '403' in error_msg or 'permission' in error_msg.lower():
                if 'no permissions for' in error_msg:
                    perm = error_msg.split('no permissions for [')[1].split(']')[0] if 'no permissions for [' in error_msg else 'unknown'
                    print(f"❌ {perm} - CANNOT get cluster info")
                    results['dont_have'].append(f"OpenSearch: {perm}")
                else:
                    print("❌ cluster:monitor/main - CANNOT get cluster info (permission denied)")
                    results['dont_have'].append("OpenSearch: cluster:monitor/main")
            else:
                print(f"⚠️  cluster:monitor/main - Error: {str(e)[:100]}")
                results['errors'].append(f"cluster:monitor/main: {str(e)[:100]}")
        
        # cluster:monitor/health
        try:
            health = client.cluster.health()
            print("✅ cluster:monitor/health - CAN get cluster health")
            results['have'].append("OpenSearch: cluster:monitor/health")
        except Exception as e:
            error_msg = str(e)
            if '403' in error_msg or 'permission' in error_msg.lower():
                if 'no permissions for' in error_msg:
                    perm = error_msg.split('no permissions for [')[1].split(']')[0] if 'no permissions for [' in error_msg else 'unknown'
                    print(f"❌ {perm} - CANNOT get cluster health")
                    if perm not in [r.split(': ')[1] for r in results['dont_have'] if ': ' in r]:
                        results['dont_have'].append(f"OpenSearch: {perm}")
                else:
                    print("❌ cluster:monitor/health - CANNOT get cluster health")
                    results['dont_have'].append("OpenSearch: cluster:monitor/health")
        
        # Test index admin permissions
        print("\n📁 Index Admin Permissions:")
        print("-" * 70)
        
        # indices:admin/get
        try:
            indices = client.cat.indices(format='json')
            print("✅ indices:admin/get - CAN list indices")
            results['have'].append("OpenSearch: indices:admin/get")
            if indices:
                print(f"   Found {len(indices)} index(es)")
            else:
                print("   No indices found (this is OK)")
        except Exception as e:
            error_msg = str(e)
            if '403' in error_msg or 'permission' in error_msg.lower():
                if 'no permissions for' in error_msg:
                    perm = error_msg.split('no permissions for [')[1].split(']')[0] if 'no permissions for [' in error_msg else 'unknown'
                    print(f"❌ {perm} - CANNOT list indices")
                    results['dont_have'].append(f"OpenSearch: {perm}")
                else:
                    print("❌ indices:admin/get - CANNOT list indices")
                    results['dont_have'].append("OpenSearch: indices:admin/get")
            else:
                print(f"⚠️  indices:admin/get - Error: {str(e)[:100]}")
        
        # indices:admin/create
        test_index = "aris-permission-test-temp"
        try:
            if client.indices.exists(index=test_index):
                client.indices.delete(index=test_index)
            
            result = client.indices.create(
                index=test_index,
                body={"settings": {"number_of_shards": 1, "number_of_replicas": 0}}
            )
            print("✅ indices:admin/create - CAN create indices")
            results['have'].append("OpenSearch: indices:admin/create")
            
            # Cleanup
            try:
                client.indices.delete(index=test_index)
            except:
                pass
        except Exception as e:
            error_msg = str(e)
            if '403' in error_msg or 'permission' in error_msg.lower():
                if 'no permissions for' in error_msg:
                    perm = error_msg.split('no permissions for [')[1].split(']')[0] if 'no permissions for [' in error_msg else 'unknown'
                    print(f"❌ {perm} - CANNOT create indices")
                    results['dont_have'].append(f"OpenSearch: {perm}")
                else:
                    print("❌ indices:admin/create - CANNOT create indices")
                    results['dont_have'].append("OpenSearch: indices:admin/create")
            elif 'already exists' in error_msg.lower():
                print("⚠️  indices:admin/create - Index already exists")
            else:
                print(f"⚠️  indices:admin/create - Error: {str(e)[:100]}")
        
        # Test data write permissions
        print("\n✍️  Data Write Permissions:")
        print("-" * 70)
        
        # Create a test index first if we can
        test_index = "aris-write-test-temp"
        index_exists = False
        try:
            if not client.indices.exists(index=test_index):
                try:
                    client.indices.create(index=test_index, body={"settings": {"number_of_shards": 1}})
                    index_exists = True
                except:
                    pass
            else:
                index_exists = True
        except:
            pass
        
        if index_exists:
            # indices:data/write/index
            try:
                result = client.index(index=test_index, body={"test": "data", "message": "permission test"})
                print("✅ indices:data/write/index - CAN write documents")
                results['have'].append("OpenSearch: indices:data/write/index")
            except Exception as e:
                error_msg = str(e)
                if '403' in error_msg or 'permission' in error_msg.lower():
                    if 'no permissions for' in error_msg:
                        perm = error_msg.split('no permissions for [')[1].split(']')[0] if 'no permissions for [' in error_msg else 'unknown'
                        print(f"❌ {perm} - CANNOT write documents")
                        results['dont_have'].append(f"OpenSearch: {perm}")
                    else:
                        print("❌ indices:data/write/index - CANNOT write documents")
                        results['dont_have'].append("OpenSearch: indices:data/write/index")
            
            # Test data read permissions
            print("\n🔎 Data Read Permissions:")
            print("-" * 70)
            
            # indices:data/read/search
            try:
                result = client.search(index=test_index, body={"query": {"match_all": {}}, "size": 1})
                print("✅ indices:data/read/search - CAN search documents")
                results['have'].append("OpenSearch: indices:data/read/search")
            except Exception as e:
                error_msg = str(e)
                if '403' in error_msg or 'permission' in error_msg.lower():
                    if 'no permissions for' in error_msg:
                        perm = error_msg.split('no permissions for [')[1].split(']')[0] if 'no permissions for [' in error_msg else 'unknown'
                        print(f"❌ {perm} - CANNOT search documents")
                        results['dont_have'].append(f"OpenSearch: {perm}")
                    else:
                        print("❌ indices:data/read/search - CANNOT search documents")
                        results['dont_have'].append("OpenSearch: indices:data/read/search")
                else:
                    print(f"⚠️  indices:data/read/search - Error: {str(e)[:100]}")
            
            # Cleanup
            try:
                client.indices.delete(index=test_index)
            except:
                pass
        else:
            print("⚠️  Cannot test write/read permissions - need create permission first")
            results['errors'].append("Cannot test write/read - no create permission")
    
except ImportError:
    print("❌ Error: opensearch-py not installed")
    print("   Install with: pip install opensearch-py requests-aws4auth")
    results['errors'].append("opensearch-py not installed")
except Exception as e:
    print(f"❌ Error: {str(e)}")
    results['errors'].append(f"OpenSearch connection: {str(e)}")

# Summary
print()
print("=" * 70)
print("PERMISSIONS SUMMARY")
print("=" * 70)
print()

print(f"✅ Permissions You HAVE ({len(results['have'])}):")
if results['have']:
    for perm in sorted(results['have']):
        print(f"   • {perm}")
else:
    print("   (None found)")

print()
print(f"❌ Permissions You DON'T HAVE ({len(results['dont_have'])}):")
if results['dont_have']:
    for perm in sorted(set(results['dont_have'])):
        print(f"   • {perm}")
else:
    print("   (All permissions available!)")

if results['errors']:
    print()
    print(f"⚠️  Errors ({len(results['errors'])}):")
    for error in results['errors']:
        print(f"   • {error}")

print()
print("=" * 70)
print("RECOMMENDATIONS")
print("=" * 70)
print()

if len(results['dont_have']) > 0:
    print("You need to request these permissions from your OpenSearch administrator:")
    print()
    print("IAM User: WaseemOS")
    print(f"IAM ARN: arn:aws:iam::975049910508:user/WaseemOS")
    print(f"Domain: {domain_name}")
    print()
    print("Required OpenSearch permissions:")
    for perm in sorted(set([p.split(': ')[1] for p in results['dont_have'] if ': ' in p])):
        print(f"   • {perm}")
else:
    print("✅ You have all necessary permissions!")

print()
print("=" * 70)

