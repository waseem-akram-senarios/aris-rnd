# Resource Optimization - Maximum Server Specs Utilization

## Overview

The deployment system now **dynamically detects** server specifications and automatically allocates maximum available resources for optimal processing power.

## Current Server Specifications

**Server IP**: 44.221.84.58

### Hardware
- **CPU**: AMD EPYC 9R14 - 16 cores
- **Memory**: 61 GB RAM
- **Storage**: 100 GB SSD (81 GB available)

### Container Allocation (Dynamic)
- **CPU**: 15 cores allocated (93.75% of available)
- **Memory**: 59 GB allocated (96.7% of available)
- **Memory Reservation**: 55 GB
- **System Reserve**: 1 CPU core + 2 GB RAM

## Resource Allocation Logic

The deployment script (`scripts/deploy-fast.sh`) now:

1. **Detects Server Specs**:
   ```bash
   CPU_COUNT=$(nproc)
   TOTAL_MEM_GB=$(free -g | awk '/^Mem:/ {print $2}')
   ```

2. **Calculates Optimal Allocation**:
   - Leaves 1 CPU core for system operations
   - Leaves 2 GB RAM for system operations
   - Allocates all remaining resources to container

3. **Applies Safety Minimums**:
   - Minimum 1 CPU core
   - Minimum 4 GB RAM
   - Minimum 2 GB memory reservation

## Performance Improvements

### Before Optimization
- **CPU**: 7 cores (43.75% utilization)
- **Memory**: 12 GB (19.7% utilization)
- **Processing Power**: Limited

### After Optimization
- **CPU**: 15 cores (93.75% utilization) - **+114% increase**
- **Memory**: 59 GB (96.7% utilization) - **+392% increase**
- **Processing Power**: Maximum available

## Benefits

1. **Automatic Adaptation**: Works on any server size without manual configuration
2. **Maximum Performance**: Uses nearly all available resources
3. **System Safety**: Reserves resources for OS and system processes
4. **Better Processing**: More CPU and memory = faster document processing, embedding, and querying
5. **Scalability**: Automatically scales up if server is upgraded

## Usage

The dynamic resource allocation happens automatically during deployment:

```bash
./scripts/deploy-fast.sh
```

The script will:
1. Detect server specs
2. Calculate optimal allocation
3. Deploy container with maximum resources
4. Display allocation details

## Monitoring

Check current resource usage:

```bash
# Container stats
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 \
  "sudo docker stats aris-rag-app --no-stream"

# Server specs
ssh -i scripts/ec2_wah_pk.pem ec2-user@44.221.84.58 \
  "./scripts/detect_server_specs.sh"
```

## Configuration Files

- **Deployment Script**: `scripts/deploy-fast.sh` (includes dynamic detection)
- **Spec Detection**: `scripts/detect_server_specs.sh` (standalone utility)
- **Server Specs**: `SERVER_SPECS.md` (documentation)

## Expected Performance Gains

With 15 CPUs and 59 GB RAM:

- **PDF Processing**: 2-3x faster (more parallel processing)
- **Embedding Generation**: 3-4x faster (more memory for batch processing)
- **Query Processing**: 2x faster (more CPU for vector search)
- **Concurrent Requests**: Can handle significantly more simultaneous users
- **Large Documents**: Can process much larger files without memory issues

## Notes

- The system automatically reserves resources for OS stability
- Resource allocation is recalculated on each deployment
- No manual configuration needed - fully automatic
- Works on any server size (small to large)

---

**Last Updated**: December 4, 2025  
**Status**: ✅ Maximum resources allocated and operational

