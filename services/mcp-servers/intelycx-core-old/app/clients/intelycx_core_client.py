import aiohttp
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class IntelycxCoreClient:
    base_url: str
    api_key: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    
    def __post_init__(self):
        """Initialize credentials from environment variables if not provided."""
        if not self.username:
            self.username = os.environ.get("INTELYCX_CORE_USERNAME")
        if not self.password:
            self.password = os.environ.get("INTELYCX_CORE_PASSWORD")

    async def login(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticate with Intelycx Core API and return JWT token."""
        login_url = f"{self.base_url}/login"
        
        login_data = {
            "username": username,
            "password": password
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(login_url, json=login_data) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"✅ Login successful for user: {username}")
                        return {
                            "success": True,
                            "jwt_token": result.get("token") or result.get("jwt_token") or result.get("access_token"),
                            "expires_in": result.get("expires_in", 3600),
                            "user_info": result.get("user", {})
                        }
                    elif response.status == 401:
                        logger.error(f"❌ Login failed for user {username}: Invalid credentials")
                        return {
                            "success": False,
                            "error": "Invalid username or password"
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Login failed for user {username}: HTTP {response.status} - {error_text}")
                        return {
                            "success": False,
                            "error": f"Login failed with status {response.status}"
                        }
        except aiohttp.ClientError as e:
            logger.error(f"❌ Login network error for user {username}: {str(e)}")
            return {
                "success": False,
                "error": f"Network error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"❌ Login unexpected error for user {username}: {str(e)}")
            return {
                "success": False,
                "error": f"Unexpected error: {str(e)}"
            }

    async def get_production_summary(self, jwt_token: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get production summary data with JWT authentication."""
        url = f"{self.base_url}/production/summary"
        
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info("✅ Production summary retrieved successfully")
                        return result
                    elif response.status == 401:
                        logger.error("❌ Production summary failed: Invalid or expired JWT token")
                        return {"error": "Authentication failed - token may be expired"}
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Production summary failed: HTTP {response.status} - {error_text}")
                        return {"error": f"API request failed with status {response.status}"}
        except Exception as e:
            logger.error(f"❌ Production summary error: {str(e)}")
            return {"error": f"Request failed: {str(e)}"}
    
    async def get_machine(self, jwt_token: str, machine_id: str) -> Dict[str, Any]:
        """Get machine information with JWT authentication."""
        url = f"{self.base_url}/machines/{machine_id}"
        
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"✅ Machine {machine_id} retrieved successfully")
                        return result
                    elif response.status == 401:
                        logger.error(f"❌ Machine {machine_id} failed: Invalid or expired JWT token")
                        return {"error": "Authentication failed - token may be expired"}
                    elif response.status == 404:
                        logger.error(f"❌ Machine {machine_id} not found")
                        return {"error": f"Machine {machine_id} not found"}
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Machine {machine_id} failed: HTTP {response.status} - {error_text}")
                        return {"error": f"API request failed with status {response.status}"}
        except Exception as e:
            logger.error(f"❌ Machine {machine_id} error: {str(e)}")
            return {"error": f"Request failed: {str(e)}"}
    
    async def get_machine_group(self, jwt_token: str, group_id: str) -> Dict[str, Any]:
        """Get machine group information with JWT authentication."""
        url = f"{self.base_url}/machine-groups/{group_id}"
        
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/json"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        result = await response.json()
                        logger.info(f"✅ Machine group {group_id} retrieved successfully")
                        return result
                    elif response.status == 401:
                        logger.error(f"❌ Machine group {group_id} failed: Invalid or expired JWT token")
                        return {"error": "Authentication failed - token may be expired"}
                    elif response.status == 404:
                        logger.error(f"❌ Machine group {group_id} not found")
                        return {"error": f"Machine group {group_id} not found"}
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Machine group {group_id} failed: HTTP {response.status} - {error_text}")
                        return {"error": f"API request failed with status {response.status}"}
        except Exception as e:
            logger.error(f"❌ Machine group {group_id} error: {str(e)}")
            return {"error": f"Request failed: {str(e)}"}
    
    async def get_fake_data(self, jwt_token: str) -> Dict[str, Any]:
        """Get fake production data for testing and development purposes with JWT authentication."""
        logger.info("✅ Generating fake production data (authenticated)")
        
        # Simulate JWT token validation (in real implementation, this would validate against the API)
        if not jwt_token or len(jwt_token) < 10:
            logger.error("❌ Invalid JWT token for fake data request")
            return {"error": "Authentication failed - invalid or missing JWT token"}
        
        # Generate comprehensive fake production data
        fake_data = {
            "timestamp": "2025-08-27T20:55:00Z",
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
                    "timestamp": "2025-08-27T19:30:00Z"
                },
                {
                    "id": "ALERT_002",
                    "type": "efficiency",
                    "severity": "low", 
                    "line_id": "LINE_001",
                    "message": "Assembly Line Alpha efficiency below target (87% vs 90%)",
                    "timestamp": "2025-08-27T20:15:00Z"
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
        
        return fake_data
