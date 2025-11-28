#!/usr/bin/env python3
"""
Comprehensive OpenSearch Permissions Test Script
Tests all permissions and generates a detailed report that can be shared with administrators.
"""
import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

# Load .env from project root (parent directory of tests/)
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path)

# Configuration
access_key = os.getenv('AWS_OPENSEARCH_ACCESS_KEY_ID')
secret_key = os.getenv('AWS_OPENSEARCH_SECRET_ACCESS_KEY')
region = os.getenv('AWS_OPENSEARCH_REGION', 'us-east-2')
domain_name = 'intelycx-os-dev'
endpoint = "https://search-intelycx-os-dev-avu6r2aoemtqc3gaojwzvmaj4u.us-east-2.es.amazonaws.com"

# Results storage
results = {
    'timestamp': datetime.now().isoformat(),
    'user_info': {
        'iam_user': 'WaseemOS',
        'iam_arn': 'arn:aws:iam::975049910508:user/WaseemOS',
        'domain': domain_name,
        'region': region,
        'endpoint': endpoint
    },
    'tests': [],
    'summary': {
        'total_tests': 0,
        'passed': 0,
        'failed': 0,
        'errors': 0
    },
    'permissions': {
        'have': [],
        'dont_have': [],
        'errors': []
    }
}

def print_header(title):
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)

def print_test(name, status, details=""):
    icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
    print(f"{icon} {name}")
    if details:
        print(f"   {details}")
    return status

def test_aws_api():
    """Test AWS API permissions via boto3"""
    print_header("1. AWS API Permissions (via boto3)")
    
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        opensearch_client = boto3.client(
            'opensearch',
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        
        # Test list_domain_names
        test_result = {
            'test': 'AWS API: list_domain_names',
            'permission': 'opensearch:ListDomainNames',
            'status': 'FAIL',
            'error': None,
            'details': ''
        }
        try:
            domains = opensearch_client.list_domain_names()
            test_result['status'] = 'PASS'
            test_result['details'] = f"Found {len(domains.get('DomainNames', []))} domain(s)"
            results['permissions']['have'].append('AWS API: list_domain_names')
            print_test("AWS API: list_domain_names", "PASS", test_result['details'])
        except ClientError as e:
            test_result['status'] = 'FAIL'
            test_result['error'] = f"{e.response['Error']['Code']}: {e.response['Error']['Message']}"
            results['permissions']['dont_have'].append('AWS API: list_domain_names')
            print_test("AWS API: list_domain_names", "FAIL", test_result['error'])
        except Exception as e:
            test_result['status'] = 'ERROR'
            test_result['error'] = str(e)
            results['permissions']['errors'].append(f"list_domain_names: {str(e)}")
            print_test("AWS API: list_domain_names", "ERROR", test_result['error'])
        
        results['tests'].append(test_result)
        results['summary']['total_tests'] += 1
        if test_result['status'] == 'PASS':
            results['summary']['passed'] += 1
        elif test_result['status'] == 'FAIL':
            results['summary']['failed'] += 1
        else:
            results['summary']['errors'] += 1
        
        # Test describe_domain
        test_result = {
            'test': 'AWS API: describe_domain',
            'permission': 'opensearch:DescribeDomain',
            'status': 'FAIL',
            'error': None,
            'details': ''
        }
        try:
            domain_info = opensearch_client.describe_domain(DomainName=domain_name)
            test_result['status'] = 'PASS'
            status = domain_info.get('DomainStatus', {})
            test_result['details'] = f"Domain status: {status.get('Processing', 'Active')}"
            results['permissions']['have'].append('AWS API: describe_domain')
            print_test("AWS API: describe_domain", "PASS", test_result['details'])
        except ClientError as e:
            test_result['status'] = 'FAIL'
            test_result['error'] = f"{e.response['Error']['Code']}: {e.response['Error']['Message']}"
            results['permissions']['dont_have'].append('AWS API: describe_domain')
            print_test("AWS API: describe_domain", "FAIL", test_result['error'])
        except Exception as e:
            test_result['status'] = 'ERROR'
            test_result['error'] = str(e)
            results['permissions']['errors'].append(f"describe_domain: {str(e)}")
            print_test("AWS API: describe_domain", "ERROR", test_result['error'])
        
        results['tests'].append(test_result)
        results['summary']['total_tests'] += 1
        if test_result['status'] == 'PASS':
            results['summary']['passed'] += 1
        elif test_result['status'] == 'FAIL':
            results['summary']['failed'] += 1
        else:
            results['summary']['errors'] += 1
            
    except ImportError:
        print_test("AWS API Tests", "ERROR", "boto3 not installed")
        results['permissions']['errors'].append("boto3 not installed")
    except Exception as e:
        print_test("AWS API Tests", "ERROR", str(e))
        results['permissions']['errors'].append(f"AWS API: {str(e)}")

def test_opensearch_http_api():
    """Test OpenSearch permissions via direct HTTP API"""
    print_header("2. OpenSearch HTTP API Permissions")
    
    try:
        import requests
        from requests_aws4auth import AWS4Auth
        
        awsauth = AWS4Auth(access_key, secret_key, region, 'es')
        
        # Test cluster:monitor/main
        test_result = {
            'test': 'OpenSearch: cluster:monitor/main',
            'permission': 'cluster:monitor/main',
            'status': 'FAIL',
            'error': None,
            'details': ''
        }
        try:
            response = requests.get(endpoint, auth=awsauth, verify=True, timeout=10)
            if response.status_code == 200:
                test_result['status'] = 'PASS'
                data = response.json()
                test_result['details'] = f"Cluster: {data.get('cluster_name', 'N/A')}"
                results['permissions']['have'].append('OpenSearch: cluster:monitor/main')
                print_test("cluster:monitor/main", "PASS", test_result['details'])
            else:
                test_result['status'] = 'FAIL'
                error_data = response.json() if response.text else {}
                error_msg = error_data.get('error', {}).get('root_cause', [{}])[0].get('reason', response.text[:200])
                test_result['error'] = f"HTTP {response.status_code}: {error_msg}"
                results['permissions']['dont_have'].append('OpenSearch: cluster:monitor/main')
                print_test("cluster:monitor/main", "FAIL", test_result['error'])
        except Exception as e:
            test_result['status'] = 'ERROR'
            test_result['error'] = str(e)
            results['permissions']['errors'].append(f"cluster:monitor/main: {str(e)}")
            print_test("cluster:monitor/main", "ERROR", test_result['error'])
        
        results['tests'].append(test_result)
        results['summary']['total_tests'] += 1
        if test_result['status'] == 'PASS':
            results['summary']['passed'] += 1
        elif test_result['status'] == 'FAIL':
            results['summary']['failed'] += 1
        else:
            results['summary']['errors'] += 1
        
        # Test indices:admin/get
        test_result = {
            'test': 'OpenSearch: indices:admin/get',
            'permission': 'indices:admin/get',
            'status': 'FAIL',
            'error': None,
            'details': ''
        }
        try:
            response = requests.get(f'{endpoint}/_cat/indices?format=json', auth=awsauth, verify=True, timeout=10)
            if response.status_code == 200:
                test_result['status'] = 'PASS'
                indices = response.json()
                test_result['details'] = f"Found {len(indices)} index(es)"
                results['permissions']['have'].append('OpenSearch: indices:admin/get')
                print_test("indices:admin/get", "PASS", test_result['details'])
            else:
                test_result['status'] = 'FAIL'
                error_data = response.json() if response.text else {}
                error_msg = error_data.get('error', {}).get('root_cause', [{}])[0].get('reason', response.text[:200])
                test_result['error'] = f"HTTP {response.status_code}: {error_msg}"
                results['permissions']['dont_have'].append('OpenSearch: indices:admin/get')
                print_test("indices:admin/get", "FAIL", test_result['error'])
        except Exception as e:
            test_result['status'] = 'ERROR'
            test_result['error'] = str(e)
            results['permissions']['errors'].append(f"indices:admin/get: {str(e)}")
            print_test("indices:admin/get", "ERROR", test_result['error'])
        
        results['tests'].append(test_result)
        results['summary']['total_tests'] += 1
        if test_result['status'] == 'PASS':
            results['summary']['passed'] += 1
        elif test_result['status'] == 'FAIL':
            results['summary']['failed'] += 1
        else:
            results['summary']['errors'] += 1
        
        # Test indices:admin/create (only if we can connect)
        if any(t['test'] == 'OpenSearch: cluster:monitor/main' and t['status'] == 'PASS' for t in results['tests']):
            test_result = {
                'test': 'OpenSearch: indices:admin/create',
                'permission': 'indices:admin/create',
                'status': 'FAIL',
                'error': None,
                'details': ''
            }
            test_index = "aris-permission-test-temp"
            try:
                # Check if exists first
                check_response = requests.head(f'{endpoint}/{test_index}', auth=awsauth, verify=True, timeout=10)
                if check_response.status_code == 200:
                    # Delete if exists
                    requests.delete(f'{endpoint}/{test_index}', auth=awsauth, verify=True, timeout=10)
                
                # Try to create
                create_body = {"settings": {"number_of_shards": 1, "number_of_replicas": 0}}
                response = requests.put(f'{endpoint}/{test_index}', 
                                      auth=awsauth, verify=True, timeout=10,
                                      json=create_body,
                                      headers={'Content-Type': 'application/json'})
                if response.status_code in [200, 201]:
                    test_result['status'] = 'PASS'
                    test_result['details'] = "Can create indices"
                    results['permissions']['have'].append('OpenSearch: indices:admin/create')
                    print_test("indices:admin/create", "PASS", test_result['details'])
                    # Cleanup
                    requests.delete(f'{endpoint}/{test_index}', auth=awsauth, verify=True, timeout=10)
                else:
                    test_result['status'] = 'FAIL'
                    error_data = response.json() if response.text else {}
                    error_msg = error_data.get('error', {}).get('root_cause', [{}])[0].get('reason', response.text[:200])
                    test_result['error'] = f"HTTP {response.status_code}: {error_msg}"
                    results['permissions']['dont_have'].append('OpenSearch: indices:admin/create')
                    print_test("indices:admin/create", "FAIL", test_result['error'])
            except Exception as e:
                test_result['status'] = 'ERROR'
                test_result['error'] = str(e)
                results['permissions']['errors'].append(f"indices:admin/create: {str(e)}")
                print_test("indices:admin/create", "ERROR", test_result['error'])
            
            results['tests'].append(test_result)
            results['summary']['total_tests'] += 1
            if test_result['status'] == 'PASS':
                results['summary']['passed'] += 1
            elif test_result['status'] == 'FAIL':
                results['summary']['failed'] += 1
            else:
                results['summary']['errors'] += 1
        
        # Test indices:data/write/index (only if we can connect and have an index)
        if any(t['test'] == 'OpenSearch: cluster:monitor/main' and t['status'] == 'PASS' for t in results['tests']):
            test_result = {
                'test': 'OpenSearch: indices:data/write/index',
                'permission': 'indices:data/write/index',
                'status': 'FAIL',
                'error': None,
                'details': ''
            }
            test_index = "aris-write-test-temp"
            try:
                # Try to create index first (might fail, but that's OK)
                create_body = {"settings": {"number_of_shards": 1, "number_of_replicas": 0}}
                requests.put(f'{endpoint}/{test_index}', 
                            auth=awsauth, verify=True, timeout=10,
                            json=create_body,
                            headers={'Content-Type': 'application/json'})
                
                # Try to write a document
                doc_body = {"test": "data", "message": "permission test", "timestamp": datetime.now().isoformat()}
                response = requests.post(f'{endpoint}/{test_index}/_doc',
                                       auth=awsauth, verify=True, timeout=10,
                                       json=doc_body,
                                       headers={'Content-Type': 'application/json'})
                if response.status_code in [200, 201]:
                    test_result['status'] = 'PASS'
                    test_result['details'] = "Can write documents"
                    results['permissions']['have'].append('OpenSearch: indices:data/write/index')
                    print_test("indices:data/write/index", "PASS", test_result['details'])
                    # Cleanup
                    requests.delete(f'{endpoint}/{test_index}', auth=awsauth, verify=True, timeout=10)
                else:
                    test_result['status'] = 'FAIL'
                    error_data = response.json() if response.text else {}
                    error_msg = error_data.get('error', {}).get('root_cause', [{}])[0].get('reason', response.text[:200])
                    test_result['error'] = f"HTTP {response.status_code}: {error_msg}"
                    results['permissions']['dont_have'].append('OpenSearch: indices:data/write/index')
                    print_test("indices:data/write/index", "FAIL", test_result['error'])
            except Exception as e:
                test_result['status'] = 'ERROR'
                test_result['error'] = str(e)
                results['permissions']['errors'].append(f"indices:data/write/index: {str(e)}")
                print_test("indices:data/write/index", "ERROR", test_result['error'])
            
            results['tests'].append(test_result)
            results['summary']['total_tests'] += 1
            if test_result['status'] == 'PASS':
                results['summary']['passed'] += 1
            elif test_result['status'] == 'FAIL':
                results['summary']['failed'] += 1
            else:
                results['summary']['errors'] += 1
        
        # Test indices:data/read/search (only if we can connect)
        if any(t['test'] == 'OpenSearch: cluster:monitor/main' and t['status'] == 'PASS' for t in results['tests']):
            test_result = {
                'test': 'OpenSearch: indices:data/read/search',
                'permission': 'indices:data/read/search',
                'status': 'FAIL',
                'error': None,
                'details': ''
            }
            test_index = "aris-search-test-temp"
            try:
                # Try to search (even if index doesn't exist, we'll get different error)
                search_body = {"query": {"match_all": {}}, "size": 1}
                response = requests.post(f'{endpoint}/{test_index}/_search',
                                        auth=awsauth, verify=True, timeout=10,
                                        json=search_body,
                                        headers={'Content-Type': 'application/json'})
                if response.status_code == 200:
                    test_result['status'] = 'PASS'
                    test_result['details'] = "Can search documents"
                    results['permissions']['have'].append('OpenSearch: indices:data/read/search')
                    print_test("indices:data/read/search", "PASS", test_result['details'])
                elif response.status_code == 404:
                    # Index doesn't exist, but we can try search anyway
                    test_result['status'] = 'FAIL'
                    test_result['error'] = "Index not found (but search permission may work)"
                    results['permissions']['dont_have'].append('OpenSearch: indices:data/read/search')
                    print_test("indices:data/read/search", "FAIL", test_result['error'])
                else:
                    test_result['status'] = 'FAIL'
                    error_data = response.json() if response.text else {}
                    error_msg = error_data.get('error', {}).get('root_cause', [{}])[0].get('reason', response.text[:200])
                    test_result['error'] = f"HTTP {response.status_code}: {error_msg}"
                    results['permissions']['dont_have'].append('OpenSearch: indices:data/read/search')
                    print_test("indices:data/read/search", "FAIL", test_result['error'])
            except Exception as e:
                test_result['status'] = 'ERROR'
                test_result['error'] = str(e)
                results['permissions']['errors'].append(f"indices:data/read/search: {str(e)}")
                print_test("indices:data/read/search", "ERROR", test_result['error'])
            
            results['tests'].append(test_result)
            results['summary']['total_tests'] += 1
            if test_result['status'] == 'PASS':
                results['summary']['passed'] += 1
            elif test_result['status'] == 'FAIL':
                results['summary']['failed'] += 1
            else:
                results['summary']['errors'] += 1
                
    except ImportError:
        print_test("OpenSearch HTTP API Tests", "ERROR", "requests or requests-aws4auth not installed")
        results['permissions']['errors'].append("Required packages not installed")
    except Exception as e:
        print_test("OpenSearch HTTP API Tests", "ERROR", str(e))
        results['permissions']['errors'].append(f"HTTP API: {str(e)}")

def print_summary():
    """Print summary and save results"""
    print_header("PERMISSIONS SUMMARY")
    
    print(f"\n✅ Permissions You HAVE ({len(results['permissions']['have'])}):")
    if results['permissions']['have']:
        for perm in sorted(results['permissions']['have']):
            print(f"   • {perm}")
    else:
        print("   (None found)")
    
    print(f"\n❌ Permissions You DON'T HAVE ({len(results['permissions']['dont_have'])}):")
    if results['permissions']['dont_have']:
        for perm in sorted(set(results['permissions']['dont_have'])):
            print(f"   • {perm}")
    else:
        print("   (All permissions available!)")
    
    if results['permissions']['errors']:
        print(f"\n⚠️  Errors ({len(results['permissions']['errors'])}):")
        for error in results['permissions']['errors']:
            print(f"   • {error}")
    
    print(f"\n📊 Test Summary:")
    print(f"   Total Tests: {results['summary']['total_tests']}")
    print(f"   Passed: {results['summary']['passed']}")
    print(f"   Failed: {results['summary']['failed']}")
    print(f"   Errors: {results['summary']['errors']}")
    
    # Save JSON report to project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    report_file = os.path.join(project_root, 'opensearch_permissions_report.json')
    with open(report_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Detailed report saved to: {report_file}")
    print("   You can share this JSON file with your administrator.")
    
    # Print key finding
    print("\n" + "=" * 80)
    print(" KEY FINDING")
    print("=" * 80)
    
    if results['permissions']['dont_have']:
        blocking_perms = [p for p in results['permissions']['dont_have'] if 'cluster:monitor/main' in p]
        if blocking_perms:
            print("\n⚠️  CRITICAL: Missing 'cluster:monitor/main' permission")
            print("   This blocks all other OpenSearch operations.")
            print("   This is the first permission that must be granted.")
        
        print("\n💡 Root Cause:")
        print("   The IAM user is not mapped to any OpenSearch role.")
        print("   The domain uses Fine-Grained Access Control (FGAC).")
        print("   AWS IAM permissions alone are not sufficient.")
        print("   The IAM user needs to be mapped to an OpenSearch role within the domain.")
    
    print("\n" + "=" * 80)

def main():
    if not access_key or not secret_key:
        print("❌ Error: OpenSearch credentials not found in .env file")
        print("   Please set AWS_OPENSEARCH_ACCESS_KEY_ID and AWS_OPENSEARCH_SECRET_ACCESS_KEY")
        sys.exit(1)
    
    print("=" * 80)
    print(" OpenSearch Permissions Test Script")
    print("=" * 80)
    print(f"\nDomain: {domain_name}")
    print(f"Endpoint: {endpoint}")
    print(f"Region: {region}")
    print(f"IAM User: {results['user_info']['iam_user']}")
    print(f"IAM ARN: {results['user_info']['iam_arn']}")
    
    # Run tests
    test_aws_api()
    test_opensearch_http_api()
    
    # Print summary
    print_summary()

if __name__ == '__main__':
    main()

