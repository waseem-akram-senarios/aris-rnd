# Your Current OpenSearch Permissions

## ✅ Permissions You HAVE

### AWS API Level (via boto3)
- ✅ **List OpenSearch domains** - Can see all available domains
- ✅ **Describe OpenSearch domains** - Can get domain information
- ✅ **Get domain endpoints** - Can retrieve connection endpoints
- ✅ **Get domain status** - Can check if domain is active

**What this means:** You can discover and connect to OpenSearch domains, but cannot perform operations on them.

## ❌ Permissions You DON'T HAVE

Based on test results and error messages, you are missing these OpenSearch-level permissions:

### Cluster Permissions
- ❌ **cluster:monitor/main** - Basic cluster monitoring
  - *Error seen:* `no permissions for [cluster:monitor/main]`

### Index Admin Permissions
- ❌ **indices:admin/get** - Get index information
  - *Error seen:* `no permissions for [indices:admin/get]`
- ❌ **indices:admin/create** - Create new indices
- ❌ **indices:admin/mapping/get** - Get index mappings
- ❌ **indices:admin/settings/get** - Get index settings

### Data Write Permissions
- ❌ **indices:data/write/index** - Write documents to indices
- ❌ **indices:data/write/bulk** - Bulk write operations

### Data Read Permissions
- ❌ **indices:data/read/search** - Search documents in indices
  - *Error seen:* `no permissions for [indices:data/read/search]`
- ❌ **indices:data/read/get** - Read individual documents

## What This Means

### You CAN:
- ✅ See what OpenSearch domains exist
- ✅ Get domain information (endpoints, status, configuration)
- ✅ Connect to the OpenSearch endpoint
- ✅ Authenticate with AWS credentials

### You CANNOT:
- ❌ Create or manage indices
- ❌ Write documents to indices
- ❌ Search documents in indices
- ❌ Read documents from indices
- ❌ Monitor cluster status
- ❌ Use OpenSearch for RAG operations

## Why This Happens

The OpenSearch domain `intelycx-os-dev` uses **Fine-Grained Access Control (FGAC)**. This means:

1. **IAM permissions alone are not enough** - Even if you have AWS IAM permissions, you need OpenSearch-level permissions
2. **You need OpenSearch role mapping** - Your IAM user must be mapped to an OpenSearch role within the domain
3. **Separate permission system** - OpenSearch has its own role-based access control separate from AWS IAM

## What You Need to Request

Contact your OpenSearch administrator and request:

### 1. Map Your IAM User to an OpenSearch Role

**Your IAM User Details:**
- **Username:** WaseemOS
- **ARN:** `arn:aws:iam::975049910508:user/WaseemOS`
- **Domain:** intelycx-os-dev

### 2. Grant These Permissions

The OpenSearch role should have these permissions:

```
Cluster Permissions:
  - cluster:monitor/main

Index Admin Permissions:
  - indices:admin/create
  - indices:admin/get
  - indices:admin/mapping/get
  - indices:admin/settings/get

Data Write Permissions:
  - indices:data/write/index
  - indices:data/write/bulk

Data Read Permissions:
  - indices:data/read/search
  - indices:data/read/get
```

### 3. Request Format

You can send this to your administrator:

```
Subject: OpenSearch Permissions Request for RAG System

Hi,

I need OpenSearch permissions for the RAG system integration.

IAM User: WaseemOS
IAM ARN: arn:aws:iam::975049910508:user/WaseemOS
Domain: intelycx-os-dev

Required Permissions:
- cluster:monitor/main
- indices:admin/create
- indices:admin/get
- indices:admin/mapping/get
- indices:data/write/index
- indices:data/write/bulk
- indices:data/read/search
- indices:data/read/get

Please map my IAM user to an OpenSearch role with these permissions.

Thanks!
```

## Alternative: Use FAISS

✅ **FAISS is fully working** and doesn't require any AWS permissions:
- All tests pass (20/20)
- No configuration needed
- Faster for most use cases
- Stores data locally
- **Recommended for immediate use**

You can use FAISS now and switch to OpenSearch later when permissions are granted.

## Summary

| Permission Type | Status | Details |
|----------------|--------|---------|
| AWS API (boto3) | ✅ Working | Can list/describe domains |
| OpenSearch Connection | ✅ Working | Can connect to endpoint |
| Authentication | ✅ Working | AWS credentials valid |
| Index Operations | ❌ Missing | Need OpenSearch role permissions |
| Data Operations | ❌ Missing | Need OpenSearch role permissions |
| Cluster Monitoring | ❌ Missing | Need OpenSearch role permissions |

**Status:** Code is working correctly. The issue is missing OpenSearch role permissions, not code bugs.

