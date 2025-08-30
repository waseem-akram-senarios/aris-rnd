"""FastMCP Core Server for Intelycx manufacturing data."""

import os
import logging
from typing import Any, Dict, Optional

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse
from .core_client import IntelycxCoreClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastMCP server
mcp = FastMCP("Intelycx Core")

# Initialize core client
core_client = IntelycxCoreClient()


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint for monitoring and Docker health checks."""
    logger.info("🏥 Health check requested")
    
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
    
    logger.info(f"✅ Health check passed: {health_status['status']}")
    return JSONResponse(content=health_status, status_code=200)


@mcp.tool
async def intelycx_login(
    username: Optional[str] = None,
    password: Optional[str] = None
) -> Dict[str, Any]:
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
    logger.info("🔧 CORE TOOL CALL: intelycx_login")
    logger.info(f"📥 TOOL INPUT: username={username}, password={'***' if password else None}")
    
    try:
        result = await core_client.login(username=username, password=password)
        
        if result.get("success"):
            logger.info("✅ CORE TOOL SUCCESS: intelycx_login - Authentication successful")
            logger.info(f"📤 TOOL OUTPUT: Login successful for user {result.get('user')}")
        else:
            logger.error(f"❌ CORE TOOL ERROR: intelycx_login - {result.get('error')}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ CORE TOOL ERROR: intelycx_login - {str(e)}")
        return {
            "success": False,
            "error": f"Login tool execution failed: {str(e)}"
        }


@mcp.tool
async def get_fake_data(
    jwt_token: str,
    data_type: Optional[str] = None
) -> Dict[str, Any]:
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
    logger.info("🔧 CORE TOOL CALL: get_fake_data")
    logger.info(f"📥 TOOL INPUT: jwt_token={'***' if jwt_token else None}, data_type={data_type}")
    
    try:
        result = await core_client.get_fake_data(jwt_token=jwt_token, data_type=data_type)
        
        # Check if there was an authentication error
        if isinstance(result, dict) and "error" in result:
            logger.error(f"❌ CORE TOOL ERROR: get_fake_data - {result.get('error')}")
            return result
        
        # Success - result is the fake data directly
        logger.info("✅ CORE TOOL SUCCESS: get_fake_data - Fake data generated successfully")
        data_size = len(str(result))
        logger.info(f"📤 TOOL OUTPUT: Generated {data_size} characters of fake manufacturing data")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ CORE TOOL ERROR: get_fake_data - {str(e)}")
        return {
            "error": f"Get fake data tool execution failed: {str(e)}"
        }


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
