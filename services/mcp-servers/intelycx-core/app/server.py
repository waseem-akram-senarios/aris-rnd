"""FastMCP Core Server for Intelycx manufacturing data."""

import os
import logging
from typing import Any, Dict, Optional, Annotated
from enum import Enum

from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field
from starlette.requests import Request
from starlette.responses import JSONResponse
from .core_client import IntelycxCoreClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastMCP server with enhanced configuration
mcp = FastMCP(
    "Intelycx Core",
    on_duplicate_tools="warn"  # Warn about duplicate tool registrations
)

# Initialize core client
core_client = IntelycxCoreClient()


# Enums for constrained values
class DataType(Enum):
    """Supported data types for manufacturing data retrieval."""
    ALL = "all"
    PRODUCTION = "production"
    INVENTORY = "inventory"
    ALERTS = "alerts"
    METRICS = "metrics"
    ENERGY = "energy"


# Pydantic models for structured responses
class LoginResponse(BaseModel):
    """Response model for login operations."""
    success: bool = Field(description="Whether the login was successful")
    jwt_token: Optional[str] = Field(None, description="JWT token for API authentication")
    expires_in: Optional[int] = Field(None, description="Token expiration time in seconds")
    expires_at: Optional[str] = Field(None, description="ISO timestamp when token expires")
    user: Optional[str] = Field(None, description="Username that was authenticated")
    error: Optional[str] = Field(None, description="Error message if unsuccessful")
    status_code: Optional[int] = Field(None, description="HTTP status code")


class ManufacturingDataResponse(BaseModel):
    """Response model for manufacturing data operations."""
    success: bool = Field(True, description="Whether the data retrieval was successful")
    timestamp: Optional[str] = Field(None, description="Data timestamp")
    facility: Optional[Dict[str, Any]] = Field(None, description="Facility information")
    production_lines: Optional[list] = Field(None, description="Production line data")
    daily_metrics: Optional[Dict[str, Any]] = Field(None, description="Daily production metrics")
    shift_data: Optional[Dict[str, Any]] = Field(None, description="Current shift information")
    alerts: Optional[list] = Field(None, description="Active alerts and notifications")
    inventory: Optional[Dict[str, Any]] = Field(None, description="Inventory status")
    energy_consumption: Optional[Dict[str, Any]] = Field(None, description="Energy usage data")
    error: Optional[str] = Field(None, description="Error message if unsuccessful")
    data_size_kb: Optional[float] = Field(None, description="Size of returned data in KB")


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for monitoring and Docker health checks."""
    # Don't log routine health checks to reduce noise
    # Only log on startup or if there are issues
    
    # Perform basic health checks
    health_status = {
        "status": "healthy",
        "service": "intelycx-core-mcp-server",
        "version": "0.1.0",
        "transport": "http",
        "core_api_configured": bool(core_client.base_url),
        "credentials_configured": bool(core_client.username and core_client.password),
        "timestamp": "2024-08-29T00:00:00Z"  # Would be actual timestamp in real implementation
    }
    
    return JSONResponse(content=health_status, status_code=200)


@mcp.tool(
    name="intelycx_login",
    description="Authenticate with Intelycx Core API and obtain JWT token for subsequent API calls",
    tags={"authentication", "core", "security"},
    meta={"version": "2.0", "category": "authentication", "author": "intelycx"},
    annotations={
        "title": "Intelycx Core Authentication",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether login was successful"},
            "jwt_token": {"type": "string", "description": "JWT authentication token"},
            "expires_in": {"type": "integer", "description": "Token expiration time in seconds"},
            "expires_at": {"type": "string", "description": "ISO timestamp when token expires"},
            "user": {"type": "string", "description": "Authenticated username"},
            "error": {"type": "string", "description": "Error message if unsuccessful"},
            "status_code": {"type": "integer", "description": "HTTP status code"}
        },
        "required": ["success"]
    }
)
async def intelycx_login(
    username: Annotated[Optional[str], Field(
        None,
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_.-]+$",
        description="Username for authentication (defaults to INTELYCX_CORE_USERNAME env var)"
    )] = None,
    password: Annotated[Optional[str], Field(
        None,
        min_length=1,
        description="Password for authentication (defaults to INTELYCX_CORE_PASSWORD env var)"
    )] = None,
    ctx: Context = None
) -> LoginResponse:
    """
    Login to Intelycx Core API and obtain JWT token for subsequent API calls.
    
    This tool authenticates with the Intelycx Core API using provided credentials
    or environment variables. The returned JWT token should be stored and used
    for all subsequent API calls that require authentication.
    
    Args:
        username: Username for authentication (optional, defaults to INTELYCX_CORE_USERNAME env var)
        password: Password for authentication (optional, defaults to INTELYCX_CORE_PASSWORD env var)
        
    Returns:
        Dictionary containing:
        - success: Boolean indicating if login was successful
        - jwt_token: JWT token for API authentication (if successful)
        - expires_in: Token expiration time in seconds
        - expires_at: ISO timestamp when token expires
        - user: Username that was authenticated
        - error: Error message (if unsuccessful)
        
    Examples:
        # Login with environment credentials
        result = intelycx_login()
        
        # Login with specific credentials
        result = intelycx_login(username="admin", password="secret")
        
        # Check result and use token
        if result["success"]:
            jwt_token = result["jwt_token"]
            # Use jwt_token for subsequent API calls
    """
    # Enhanced multi-stage progress with structured logging and notifications
    await ctx.info(
        "🔧 Starting Intelycx Core authentication...",
        extra={
            "stage": "authentication_start",
            "username": username or "from_environment",
            "api_url": core_client.base_url,
            "tool_version": "2.0"
        }
    )
    await ctx.report_progress(progress=10, total=100)
    
    # Notify start of authentication process
    await ctx.notify("Authentication process initiated", level="info")
    
    # Infrastructure logging only
    logger.debug(f"Login attempt: username={username}, password={'***' if password else None}")
    
    try:
        await ctx.info(
            "🔐 Connecting to Intelycx Core API...",
            extra={"stage": "api_connection", "endpoint": "/login"}
        )
        await ctx.report_progress(progress=30, total=100)
        
        await ctx.info(
            "📡 Sending authentication request...",
            extra={"stage": "auth_request"}
        )
        await ctx.report_progress(progress=60, total=100)
        
        result = await core_client.login(username=username, password=password)
        
        if result.get("success"):
            await ctx.info(
                f"✅ Authentication successful for user: {result.get('user')}",
                extra={
                    "stage": "auth_success",
                    "user": result.get('user'),
                    "expires_in": result.get('expires_in'),
                    "token_length": len(result.get('jwt_token', ''))
                }
            )
            await ctx.report_progress(progress=100, total=100)
            await ctx.notify(f"Successfully authenticated as {result.get('user')}", level="success")
            logger.debug("Authentication successful")
            
            # Return structured response using Pydantic model
            return LoginResponse(**result)
        else:
            await ctx.error(
                f"❌ Authentication failed: {result.get('error')}",
                extra={
                    "stage": "auth_failure",
                    "error_type": "authentication_failed",
                    "status_code": result.get('status_code')
                }
            )
            await ctx.notify(f"Authentication failed: {result.get('error')}", level="error")
            logger.error(f"Authentication failed: {result.get('error')}")
            
            # Return structured error response
            return LoginResponse(**result)
        
    except Exception as e:
        error_msg = f"Login tool execution failed: {str(e)}"
        await ctx.error(
            f"❌ Login error: {str(e)}",
            extra={
                "stage": "auth_exception",
                "error_type": "exception",
                "exception_class": type(e).__name__
            }
        )
        await ctx.notify(f"Authentication error: {str(e)}", level="error")
        logger.error(f"Login tool error: {str(e)}")
        
        # Return structured error response
        return LoginResponse(
            success=False,
            error=error_msg
        )


@mcp.tool(
    name="get_fake_data",
    description="Generate comprehensive fake manufacturing data for testing and development with JWT authentication",
    tags={"manufacturing", "data", "testing", "development"},
    meta={"version": "2.0", "category": "data_access", "author": "intelycx"},
    annotations={
        "title": "Manufacturing Data Generator",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    },
    output_schema={
        "type": "object",
        "properties": {
            "success": {"type": "boolean", "description": "Whether data generation was successful"},
            "timestamp": {"type": "string", "description": "Data generation timestamp"},
            "facility": {"type": "object", "description": "Facility information"},
            "production_lines": {"type": "array", "description": "Production line data"},
            "daily_metrics": {"type": "object", "description": "Daily production metrics"},
            "shift_data": {"type": "object", "description": "Current shift information"},
            "alerts": {"type": "array", "description": "Active alerts and notifications"},
            "inventory": {"type": "object", "description": "Inventory status"},
            "energy_consumption": {"type": "object", "description": "Energy usage data"},
            "error": {"type": "string", "description": "Error message if unsuccessful"},
            "data_size_kb": {"type": "number", "description": "Size of returned data in KB"}
        },
        "required": ["success"]
    }
)
async def get_fake_data(
    jwt_token: Annotated[str, Field(
        description="Valid JWT token from intelycx_login (required for authentication)",
        min_length=10
    )],
    data_type: DataType = DataType.ALL,
    ctx: Context = None
) -> ManufacturingDataResponse:
    """
    Generate comprehensive fake manufacturing data for testing and development.
    
    This tool returns static fake manufacturing data and does NOT make API calls.
    It only validates that a JWT token is provided for authentication.
    The returned data includes production lines, machines, alerts, inventory, and metrics.
    
    Args:
        jwt_token: Valid JWT token from intelycx_login (required for authentication)
        data_type: Optional type of data to retrieve (currently ignored, returns all data)
        
    Returns:
        Dictionary containing comprehensive fake manufacturing data with:
        - timestamp: Current timestamp
        - facility: Facility information (name, location, machine counts)
        - production_lines: Array of production lines with machines and metrics
        - daily_metrics: Production metrics (units, efficiency, OEE, quality)
        - shift_data: Current shift information and operators
        - alerts: Active alerts and notifications
        - inventory: Raw materials and finished goods status
        - energy_consumption: Power usage and efficiency data
        
    Examples:
        # Get fake manufacturing data
        result = get_fake_data(jwt_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...")
        
        # The result contains comprehensive manufacturing data:
        # - 2 production lines with 6 machines total
        # - Daily production metrics and efficiency data
        # - Current shift information
        # - Active maintenance and efficiency alerts
        # - Inventory levels for raw materials and finished goods
        # - Energy consumption and cost data
    """
    # Enhanced multi-stage progress with structured logging and notifications
    await ctx.info(
        "🔧 Starting fake data generation...",
        extra={
            "stage": "data_generation_start",
            "data_type": data_type.value,
            "token_provided": bool(jwt_token),
            "tool_version": "2.0"
        }
    )
    await ctx.report_progress(progress=5, total=100)
    
    # Notify start of data generation
    await ctx.notify(f"Generating {data_type.value} manufacturing data", level="info")
    
    # Infrastructure logging only
    logger.debug(f"get_fake_data called: jwt_token={'***' if jwt_token else None}, data_type={data_type}")
    
    try:
        # Stage 1: Token validation (5-15%)
        await ctx.info(
            "🔐 Validating JWT token...",
            extra={"stage": "token_validation", "token_length": len(jwt_token) if jwt_token else 0}
        )
        await ctx.report_progress(progress=15, total=100)
        
        result = await core_client.get_fake_data(jwt_token=jwt_token, data_type=data_type.value)
        
        # Check if there was an authentication error
        if isinstance(result, dict) and "error" in result:
            await ctx.error(
                f"❌ Token validation failed: {result.get('error')}",
                extra={
                    "stage": "token_validation_failed",
                    "error_type": "authentication_failed"
                }
            )
            await ctx.notify(f"Token validation failed: {result.get('error')}", level="error")
            logger.error(f"Token validation failed: {result.get('error')}")
            
            # Return structured error response
            return ManufacturingDataResponse(
                success=False,
                error=result.get('error')
            )
        
        # Stage 2: Generate facility data (15-30%)
        await ctx.info(
            "🏭 Generating facility information...",
            extra={
                "stage": "facility_data",
                "facility_name": "Intelycx Manufacturing Plant A"
            }
        )
        await ctx.report_progress(progress=30, total=100)
        
        # Stage 3: Generate production lines (30-50%)
        await ctx.info(
            "⚙️ Generating production line data...",
            extra={
                "stage": "production_lines",
                "lines_count": 2,
                "machines_per_line": 3
            }
        )
        await ctx.report_progress(progress=50, total=100)
        
        # Stage 4: Generate metrics and alerts (50-70%)
        await ctx.info(
            "📊 Generating metrics and alerts...",
            extra={
                "stage": "metrics_alerts",
                "metrics_types": ["daily", "shift", "efficiency"],
                "alert_count": 2
            }
        )
        await ctx.report_progress(progress=70, total=100)
        
        # Stage 5: Generate inventory data (70-85%)
        await ctx.info(
            "📦 Generating inventory data...",
            extra={
                "stage": "inventory_data",
                "categories": ["raw_materials", "finished_goods"]
            }
        )
        await ctx.report_progress(progress=85, total=100)
        
        # Stage 6: Generate energy data and finalize (85-100%)
        await ctx.info(
            "⚡ Generating energy consumption data...",
            extra={
                "stage": "energy_data",
                "current_usage_kw": 1247.5
            }
        )
        await ctx.report_progress(progress=95, total=100)
        
        # Success - result is the fake data directly
        data_size = len(str(result))
        data_size_kb = round(data_size / 1024, 2)
        
        await ctx.info(
            f"✅ Generated comprehensive manufacturing data successfully!",
            extra={
                "stage": "generation_complete",
                "data_size_chars": data_size,
                "data_size_kb": data_size_kb,
                "sections": ["facility", "production_lines", "daily_metrics", "shift_data", "alerts", "inventory", "energy_consumption"]
            }
        )
        await ctx.report_progress(progress=100, total=100)
        await ctx.notify(f"Manufacturing data generated successfully ({data_size_kb} KB)", level="success")
        
        logger.debug(f"Fake data generated successfully: {data_size} characters")
        
        # Return structured response with metadata
        if isinstance(result, dict):
            result["success"] = True
            result["data_size_kb"] = data_size_kb
            return ManufacturingDataResponse(**result)
        else:
            return ManufacturingDataResponse(
                success=True,
                data_size_kb=data_size_kb,
                **result if isinstance(result, dict) else {}
            )
        
    except Exception as e:
        error_msg = f"Get fake data tool execution failed: {str(e)}"
        await ctx.error(
            f"❌ Data generation error: {str(e)}",
            extra={
                "stage": "generation_exception",
                "error_type": "exception",
                "exception_class": type(e).__name__
            }
        )
        await ctx.notify(f"Data generation error: {str(e)}", level="error")
        logger.error(f"get_fake_data error: {str(e)}")
        
        # Return structured error response
        return ManufacturingDataResponse(
            success=False,
            error=error_msg
        )


def main():
    """Main entry point for the server."""
    logger.info("🚀 Starting Intelycx Core MCP Server with FastMCP")
    
    # Log configuration
    logger.info(f"📡 Core API URL: {core_client.base_url}")
    logger.info(f"🔐 Credentials configured: {bool(core_client.username and core_client.password)}")
    
    # Run HTTP server on port 8080
    mcp.run(transport="http", host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
