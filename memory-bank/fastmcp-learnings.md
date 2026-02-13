# FastMCP Integration Learnings

## Critical Issues Resolved

### Docker Network Connectivity
**Problem**: DNS resolution failure between ARIS containers and Intelycx API
- **Root Cause**: `intelycx-api-1` on `intelycx_intelycx_default` network, ARIS containers on `intelycx_default` network
- **Solution**: Connect ARIS containers to correct network: `docker network connect intelycx_intelycx_default`
- **Permanent Fix**: Update docker-compose.yml to use `name: intelycx_intelycx_default`

### FastMCP Serialization Issues
**Problem**: "Object of type Root/ModelName is not JSON serializable" in Bedrock LLM
- **Root Cause**: FastMCP Client returns Pydantic model objects in `result.data`, not plain dictionaries
- **Discovery**: FastMCP design requires manual deserialization for external system integration
- **Solution**: Comprehensive object conversion function in `MCPServerManager.execute_tool()`

## FastMCP Design Patterns

### Server-Side Best Practices
- ✅ **Use Pydantic models** for return types (not `Dict[str, Any]`)
- ✅ **Remove `output_schema` parameter** - doesn't exist in FastMCP API
- ✅ **Let FastMCP infer schemas** from Pydantic model structure
- ✅ **Use proper annotations** with Field validation

### Client-Side Reality
- **`result.data` contains Pydantic objects** - NOT plain dictionaries as documentation suggests
- **Manual conversion required** for JSON serialization with external systems
- **Recursive conversion needed** for nested FastMCP objects

### Object Conversion Logic
```python
def convert_root_objects(obj):
    # Detect FastMCP objects: Root, types.ModelName, or Pydantic models
    obj_type_str = str(type(obj))
    is_fastmcp_object = (
        'Root' in obj_type_str or 
        'types.' in obj_type_str or  # FastMCP Pydantic models
        (hasattr(obj, 'model_dump') and hasattr(obj, '__dict__'))
    )
    
    if is_fastmcp_object:
        # Convert using model_dump() or dict() methods
        if hasattr(obj, 'model_dump'):
            obj = obj.model_dump()
        # ... recursive handling for nested structures
```

## Network Configuration Requirements

### Docker Network Setup
- **ARIS Agent**: Must be on `intelycx_intelycx_default` network
- **MCP Servers**: Must be on `intelycx_intelycx_default` network  
- **Intelycx API**: Already on `intelycx_intelycx_default` network
- **Critical**: All containers must share same network for DNS resolution

### Docker Compose Configuration
```yaml
networks:
  intelycx_net:
    external: true
    name: intelycx_intelycx_default  # Correct network name
```

## Error Handling Patterns

### Authentication Error Handling
```python
# Fixed: Check for None values before calling .lower()
if tool_name != "intelycx_login" and isinstance(result, dict) and "error" in result and result["error"]:
    error_msg = str(result["error"]).lower()
```

### MCP Server Manager Error Handling
- **Comprehensive logging** for debugging FastMCP object types
- **Fallback conversion** to string if all else fails
- **JSON serialization testing** before returning results

## Lessons Learned

### FastMCP Framework Understanding
1. **Documentation vs Reality**: `result.data` contains Pydantic objects, not plain dicts
2. **Serialization Responsibility**: Applications must handle conversion for external systems
3. **Invalid Parameters**: `output_schema` parameter doesn't exist in FastMCP
4. **Best Practices**: Use Pydantic models for structured, type-safe responses

### Debugging Approach
1. **Network First**: Always check Docker network connectivity for container communication issues
2. **Object Types**: Log actual object types to understand FastMCP behavior
3. **Recursive Issues**: FastMCP objects can be nested, requiring recursive conversion
4. **External Integration**: Consider JSON serialization requirements when integrating with external systems

### Production Readiness
- ✅ **Network connectivity** resolved and documented
- ✅ **Authentication flow** working end-to-end
- ✅ **Tool execution** successful with all 4 tools operational
- ✅ **Error handling** robust and comprehensive
- ✅ **FastMCP compliance** following documented best practices
