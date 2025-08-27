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
