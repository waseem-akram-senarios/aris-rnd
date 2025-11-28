"""Client for Intelycx Core API interactions."""

import logging
import os
from typing import Any, Dict, Optional
import httpx
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class IntelycxCoreClient:
    """Client for interacting with Intelycx Core API."""
    
    def __init__(self, base_url: Optional[str] = None):
        """Initialize the Intelycx Core client.
        
        Args:
            base_url: Base URL for the Intelycx Core API
        """
        self.base_url = base_url or os.environ.get("INTELYCX_CORE_BASE_URL", "http://intelycx-api-1:8002")
        self.username = os.environ.get("INTELYCX_CORE_USERNAME")
        self.password = os.environ.get("INTELYCX_CORE_PASSWORD")
        
        # JWT token storage
        self._jwt_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
        
        logger.info(f"🔧 Initialized Intelycx Core client with base URL: {self.base_url}")
        
        if not self.username or not self.password:
            logger.warning("⚠️ INTELYCX_CORE_USERNAME or INTELYCX_CORE_PASSWORD not set")
    
    async def login(self, username: Optional[str] = None, password: Optional[str] = None) -> Dict[str, Any]:
        """
        Login to Intelycx Core API and obtain JWT token.
        
        Args:
            username: Username for authentication (defaults to env var)
            password: Password for authentication (defaults to env var)
            
        Returns:
            Dictionary with login result and JWT token
        """
        # Use provided credentials or fall back to environment variables
        auth_username = username or self.username
        auth_password = password or self.password
        
        if not auth_username or not auth_password:
            error_msg = "Username and password are required for login"
            logger.error(f"❌ {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
        
        login_url = f"{self.base_url}/login"
        login_data = {
            "username": auth_username,
            "password": auth_password
        }
        
        try:
            logger.debug(f"Attempting login to {login_url} with username: {auth_username}")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    login_url,
                    json=login_data,
                    headers={"Content-Type": "application/json"},
                    timeout=30.0
                )
                
                logger.debug(f"Login response status: {response.status_code}")
                
                if response.status_code == 200:
                    response_data = response.json()
                    
                    # Extract JWT token from response
                    jwt_token = response_data.get("access_token") or response_data.get("token")
                    
                    if jwt_token:
                        # Store token and set expiration (assume 1 hour if not specified)
                        self._jwt_token = jwt_token
                        expires_in = response_data.get("expires_in", 3600)  # Default 1 hour
                        self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                        
                        logger.debug(f"Login successful, token expires at: {self._token_expires_at}")
                        
                        return {
                            "success": True,
                            "jwt_token": jwt_token,
                            "expires_in": expires_in,
                            "expires_at": self._token_expires_at.isoformat(),
                            "user": auth_username,
                            "message": "Login successful"
                        }
                    else:
                        error_msg = "No JWT token found in login response"
                        logger.error(error_msg)
                        return {
                            "success": False,
                            "error": error_msg,
                            "response": response_data
                        }
                else:
                    error_msg = f"Login failed with status {response.status_code}"
                    logger.error(error_msg)
                    
                    try:
                        error_details = response.json()
                    except:
                        error_details = response.text
                    
                    return {
                        "success": False,
                        "error": error_msg,
                        "status_code": response.status_code,
                        "details": error_details
                    }
                    
        except httpx.TimeoutException as e:
            error_msg = f"Login request timed out to {login_url}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.exception("Timeout exception details:")
            return {
                "success": False,
                "error": error_msg,
                "error_type": "timeout"
            }
        except httpx.ConnectError as e:
            error_msg = f"Connection error to {login_url}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.exception("Connection error details:")
            return {
                "success": False,
                "error": error_msg,
                "error_type": "connection_error",
                "base_url": self.base_url,
                "login_url": login_url
            }
        except httpx.HTTPError as e:
            error_msg = f"HTTP error during login to {login_url}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.exception("HTTP error details:")
            return {
                "success": False,
                "error": error_msg,
                "error_type": "http_error"
            }
        except Exception as e:
            error_msg = f"Login request failed to {login_url}: {str(e)}"
            logger.error(f"❌ {error_msg}")
            logger.exception("Exception details:")
            return {
                "success": False,
                "error": error_msg,
                "error_type": type(e).__name__,
                "base_url": self.base_url,
                "login_url": login_url
            }
    
    def is_token_valid(self) -> bool:
        """Check if the current JWT token is valid and not expired."""
        if not self._jwt_token:
            return False
        
        if not self._token_expires_at:
            # If no expiration time, assume it's still valid
            return True
        
        # Check if token expires in the next 5 minutes (buffer for safety)
        buffer_time = datetime.now() + timedelta(minutes=5)
        return self._token_expires_at > buffer_time
    
    def get_jwt_token(self) -> Optional[str]:
        """Get the current JWT token if valid."""
        if self.is_token_valid():
            return self._jwt_token
        return None
    
    async def get_fake_data(self, jwt_token: str, data_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate fake manufacturing data for testing and development purposes.
        
        This method returns static fake data and does NOT make API calls.
        It only validates that a JWT token is provided for authentication.
        
        Args:
            jwt_token: JWT token for authentication (validates token exists)
            data_type: Optional type of data to retrieve (currently ignored)
            
        Returns:
            Dictionary with comprehensive fake manufacturing data
        """
        logger.debug("Generating fake production data")
        
        # Simple JWT token validation - just check it exists and looks valid
        if not jwt_token or len(jwt_token) < 10:
            logger.debug("Invalid JWT token provided")
            return {"error": "Authentication failed - invalid or missing JWT token"}
        
        logger.debug(f"Generating fake data, type: {data_type or 'all'}")
        
        # Generate comprehensive fake production data (same as old implementation)
        fake_data = {
            "timestamp": "2025-08-30T00:00:00Z",
            "facility": {
                "name": "Intelycx Manufacturing Plant A",
                "location": "Detroit, Michigan", 
                "total_machines": 24,
                "active_machines": 22,
                "maintenance_machines": 2
            },
            "production_lines": [
                {
                    "line_id": "LINE_001",
                    "name": "Assembly Line Alpha",
                    "status": "running",
                    "efficiency": 0.87,
                    "current_output": 145,
                    "target_output": 160,
                    "machines": [
                        {"machine_id": "M001", "name": "CNC Mill 1", "status": "running", "efficiency": 0.92},
                        {"machine_id": "M002", "name": "CNC Mill 2", "status": "running", "efficiency": 0.89},
                        {"machine_id": "M003", "name": "Assembly Robot 1", "status": "running", "efficiency": 0.95}
                    ]
                },
                {
                    "line_id": "LINE_002", 
                    "name": "Assembly Line Beta",
                    "status": "running",
                    "efficiency": 0.91,
                    "current_output": 132,
                    "target_output": 140,
                    "machines": [
                        {"machine_id": "M004", "name": "CNC Mill 3", "status": "running", "efficiency": 0.88},
                        {"machine_id": "M005", "name": "CNC Mill 4", "status": "maintenance", "efficiency": 0.0},
                        {"machine_id": "M006", "name": "Assembly Robot 2", "status": "running", "efficiency": 0.93}
                    ]
                }
            ],
            "daily_metrics": {
                "total_units_produced": 2847,
                "target_units": 3200,
                "efficiency_percentage": 88.97,
                "downtime_minutes": 47,
                "quality_rate": 0.96,
                "oee": 0.85
            },
            "shift_data": {
                "current_shift": "day",
                "shift_start": "06:00",
                "shift_end": "14:00",
                "operators_on_duty": 18,
                "supervisor": "Mike Johnson"
            },
            "alerts": [
                {
                    "id": "ALERT_001",
                    "type": "maintenance",
                    "severity": "medium",
                    "machine_id": "M005",
                    "message": "Scheduled maintenance required for CNC Mill 4",
                    "timestamp": "2025-08-30T00:00:00Z"
                },
                {
                    "id": "ALERT_002",
                    "type": "efficiency",
                    "severity": "low", 
                    "line_id": "LINE_001",
                    "message": "Assembly Line Alpha efficiency below target (87% vs 90%)",
                    "timestamp": "2025-08-30T00:00:00Z"
                }
            ],
            "inventory": {
                "raw_materials": {
                    "steel_sheets": {"quantity": 1247, "unit": "pieces", "status": "adequate"},
                    "aluminum_bars": {"quantity": 892, "unit": "pieces", "status": "low"},
                    "electronic_components": {"quantity": 3456, "unit": "pieces", "status": "adequate"}
                },
                "finished_goods": {
                    "product_a": {"quantity": 234, "unit": "pieces", "status": "ready_to_ship"},
                    "product_b": {"quantity": 156, "unit": "pieces", "status": "quality_check"}
                }
            },
            "energy_consumption": {
                "current_usage_kw": 1247.5,
                "daily_consumption_kwh": 28945.2,
                "efficiency_rating": "B+",
                "cost_per_hour": 124.75
            }
        }
        
        logger.debug(f"Generated fake data with {len(fake_data)} top-level sections")
        return fake_data
