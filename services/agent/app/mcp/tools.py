"""MCP tools for Intelycx Core API integration."""

import logging
from typing import Dict, Any, List
from ..clients.intelycx_core_client import IntelycxCoreClient

logger = logging.getLogger(__name__)


class IntelycxCoreTools:
    """MCP tools wrapper for Intelycx Core API."""
    
    def __init__(self, client: IntelycxCoreClient):
        self.client = client
        self.logger = logger
    
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get all tool definitions in Bedrock format."""
        return [
            {
                "toolSpec": {
                    "name": "get_machine",
                    "description": "Get detailed information about a specific machine including status, location, maintenance schedule, and performance metrics.",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "machine_id": {
                                    "type": "string",
                                    "description": "The unique identifier of the machine"
                                }
                            },
                            "required": ["machine_id"]
                        }
                    }
                }
            },
            {
                "toolSpec": {
                    "name": "get_machine_group",
                    "description": "Get comprehensive information about a machine group including all machines, performance metrics, shift schedules, and capacity information.",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "group_id": {
                                    "type": "string",
                                    "description": "The unique identifier of the machine group"
                                }
                            },
                            "required": ["group_id"]
                        }
                    }
                }
            },
            {
                "toolSpec": {
                    "name": "get_production_summary",
                    "description": "Get production summary data and metrics for analysis and reporting.",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "params": {
                                    "type": "object",
                                    "description": "Parameters for filtering production data",
                                    "properties": {
                                        "date_from": {
                                            "type": "string",
                                            "description": "Start date for data range (YYYY-MM-DD)"
                                        },
                                        "date_to": {
                                            "type": "string",
                                            "description": "End date for data range (YYYY-MM-DD)"
                                        },
                                        "machine_ids": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "List of machine IDs to filter by"
                                        }
                                    }
                                }
                            },
                            "required": ["params"]
                        }
                    }
                }
            }
        ]
    
    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool by name with given arguments."""
        try:
            if tool_name == "get_machine":
                machine_id = arguments.get("machine_id")
                if not machine_id:
                    return {"error": "machine_id is required"}
                
                result = await self.client.get_machine(machine_id)
                return {"success": True, "data": result}
                
            elif tool_name == "get_machine_group":
                group_id = arguments.get("group_id")
                if not group_id:
                    return {"error": "group_id is required"}
                
                result = await self.client.get_machine_group(group_id)
                return {"success": True, "data": result}
                
            elif tool_name == "get_production_summary":
                params = arguments.get("params", {})
                result = await self.client.get_production_summary(params)
                return {"success": True, "data": result}
                
            else:
                return {"error": f"Unknown tool: {tool_name}"}
                
        except Exception as e:
            self.logger.error(f"Error executing tool {tool_name}: {str(e)}")
            return {"error": f"Tool execution failed: {str(e)}"}
    
    def get_tool_names(self) -> List[str]:
        """Get list of available tool names."""
        return ["get_machine", "get_machine_group", "get_production_summary"]
