from .base import BaseAgent, AgentResponse
from typing import Any, Dict, Optional, List, Callable, Awaitable
from pathlib import Path
from ..core.files import FileProcessor, get_document_content_from_s3
from ..llm.bedrock import BedrockClient
from ..core.memory import SessionMemoryManager
from ..mcp import MCPServerManager
from ..config.settings import load_settings
import logging
import os
import json
from datetime import datetime


class ManufacturingAgent(BaseAgent):
    def __init__(self) -> None:
        self._settings = load_settings()
        self._bedrock = BedrockClient(region=self._settings.BEDROCK_REGION or "us-east-2")
        self._logger = logging.getLogger("agent.manufacturing")
        self._model_id_override: Optional[str] = None
        self._temperature_override: Optional[float] = None
        self._messages: list[dict] = []  # in-connection conversation memory
        self._file_processor = FileProcessor(aws_region=self._settings.BEDROCK_REGION or "us-east-2")
        self._pending_file_content: Optional[str] = None  # Store file content to inject
        
        # JWT token management for Intelycx Core API
        self._intelycx_jwt_token: Optional[str] = None
        self._intelycx_user: Optional[str] = None
        
        # Initialize MCP server manager
        # Try multiple possible locations for the config file
        possible_paths = [
            Path(__file__).parent.parent.parent / "mcp_servers.json",  # Development
            Path("/app/mcp_servers.json"),  # Docker container
            Path("mcp_servers.json")  # Current directory fallback
        ]
        
        config_path = None
        for path in possible_paths:
            if path.exists():
                config_path = str(path)
                self._logger.info(f"📁 Found MCP config at: {config_path}")
                break
        
        if not config_path:
            self._logger.warning("No MCP config file found, using default path")
            config_path = "mcp_servers.json"
        
        self._mcp_manager = MCPServerManager(config_path=config_path)
        self._mcp_initialized = False
        
        # Progress callback for chain of thought messages
        self._progress_callback: Optional[Callable[[str], Awaitable[None]]] = None
        
        # Initialize session memory manager
        self._memory = SessionMemoryManager(
            auto_store_results=True,
            max_size_mb=50.0  # Reasonable limit for session memory
        )

    def set_progress_callback(self, callback: Optional[Callable[[str], Awaitable[None]]]) -> None:
        """Set a callback function to send progress updates during processing."""
        self._progress_callback = callback

    async def _send_progress(self, message: str) -> None:
        """Send a progress update if callback is available."""
        if self._progress_callback:
            try:
                await self._progress_callback(message)
            except Exception as e:
                self._logger.warning(f"Failed to send progress update: {e}")

    # Memory management is now handled by SessionMemoryManager

    async def process_message(self, message: str) -> AgentResponse:
        # Minimal LLM call to Bedrock (no tools yet)
        model_id = self._model_id_override or "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
        temperature = self._temperature_override if self._temperature_override is not None else 0.1
        self._logger.info(
            f"Starting ManufacturingAgent with model={model_id} region={self._settings.BEDROCK_REGION} temp={temperature}"
        )        

        # Check if we have pending file content to inject
        if self._pending_file_content:
            enhanced_message = self._pending_file_content
            self._pending_file_content = None  # Clear after use
            self._logger.info(f"Injected file content into message (enhanced length: {len(enhanced_message)})")
        else:
            enhanced_message = message or ""

        # Append user message to in-session memory
        self._messages.append({"role": "user", "content": [{"text": enhanced_message}]})

        # Start MCP servers if not already started
        if not self._mcp_initialized:
            await self._send_progress("Initializing manufacturing systems...")
            self._logger.info("🚀 Starting MCP servers...")
            start_results = await self._mcp_manager.start_all_servers()
            self._logger.info(f"📊 MCP START RESULTS: {start_results}")
            self._mcp_initialized = True
            
            # Automatically authenticate with Intelycx Core if not already authenticated
            if not self._intelycx_jwt_token and "intelycx-core" in self._mcp_manager.connections:
                await self._send_progress("Authenticating with manufacturing systems...")
                self._logger.info("🔑 Attempting automatic authentication with Intelycx Core...")
                try:
                    # Get credentials from environment
                    username = os.environ.get("INTELYCX_CORE_USERNAME")
                    password = os.environ.get("INTELYCX_CORE_PASSWORD")
                    
                    if username and password:
                        auth_result = await self._mcp_manager.execute_tool("intelycx_login", {
                            "username": username,
                            "password": password
                        })
                        if auth_result.get("success"):
                            self._intelycx_jwt_token = auth_result.get("jwt_token")
                            self._intelycx_user = username
                            await self._send_progress("Authentication successful. Ready to access manufacturing data...")
                            self._logger.info(f"✅ Automatic authentication successful for user: {username}")
                        else:
                            await self._send_progress("Authentication failed. Limited functionality available...")
                            self._logger.warning(f"⚠️ Automatic authentication failed: {auth_result.get('error', 'Unknown error')}")
                    else:
                        await self._send_progress("Authentication credentials not configured...")
                        self._logger.warning("⚠️ Missing INTELYCX_CORE_USERNAME or INTELYCX_CORE_PASSWORD environment variables")
                except Exception as e:
                    await self._send_progress("Authentication error occurred...")
                    self._logger.error(f"❌ Automatic authentication error: {str(e)}")
            elif not self._intelycx_jwt_token:
                await self._send_progress("Manufacturing core system not available. Limited functionality...")
                self._logger.warning("⚠️ Intelycx Core server not connected - skipping authentication")
        
        # Get available tools from MCP servers dynamically
        await self._send_progress("Loading available tools...")
        tools = []
        self._logger.info(f"🔍 MCP SERVERS: Found {len(self._mcp_manager.servers)} configured servers")
        self._logger.info(f"🔗 MCP CONNECTIONS: {len(self._mcp_manager.connections)} active connections")
        
        # Dynamically discover tools from connected MCP servers
        try:
            discovered_tools = await self._mcp_manager.list_tools()
            for tool in discovered_tools:
                # Convert MCP tool format to Bedrock tool format
                bedrock_tool = {
                    "toolSpec": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "inputSchema": {
                            "json": tool["inputSchema"]
                        }
                    }
                }
                tools.append(bedrock_tool)
                self._logger.info(f"🔧 Discovered tool: {tool['name']} from {tool['server']}")
            
            self._logger.info(f"🎯 DISCOVERED {len(discovered_tools)} tools from MCP servers")
            
        except Exception as e:
            self._logger.error(f"❌ Error discovering tools from MCP servers: {str(e)}")
            # Fallback: no tools from MCP servers
            self._logger.warning("⚠️ Falling back to no MCP tools due to discovery error")
        # Memory management is now handled internally, not exposed as tools
        
        self._logger.info(f"🎯 TOTAL TOOLS AVAILABLE: {len(tools)}")
        
        # Create system prompt based on tool availability
        if tools:
            auth_status = ""
            if self._intelycx_jwt_token:
                auth_status = " You are authenticated and ready to access Intelycx Core manufacturing data."
            else:
                auth_status = " Manufacturing data access is currently unavailable due to authentication issues."
            
            system_prompt = f"You are ARIS, a helpful manufacturing assistant with access to production data tools, email capabilities, and session memory management. You can query machine information, machine group details, production summaries, and send email notifications.{auth_status} ALWAYS use the available tools when users ask about machines, production lines, manufacturing metrics, or need to send emails/notifications. Never make up or guess information - only provide data from actual tool calls. You have session memory capabilities - when retrieving data, you can store it in variables using the 'result_variable_name' parameter for later reference. Use memory management tools to list, retrieve, or clear stored variables as needed. Maintain context across the conversation and remember user-provided details such as their name during this session. When documents are provided, analyze them and answer questions based on their content."
        else:
            system_prompt = "You are ARIS, a helpful manufacturing assistant. Currently, I don't have access to production data tools or email capabilities, so I cannot provide specific information about machines, machine groups, production metrics, or send notifications. Please let the user know that the tools are temporarily unavailable and suggest they try again later. Never make up or fabricate manufacturing data. Be honest about your limitations."
        
        # Use the enhanced converse method with tools
        await self._send_progress("Processing your request...")
        text = await self._bedrock.converse(
            model_id=model_id,
            messages=self._messages[-20:],
            tools=tools,
            tool_executor=self._create_tool_executor(),
            system=[{"text": system_prompt}],
            temperature=temperature,
        )

        # Append assistant reply to memory
        self._messages.append({"role": "assistant", "content": [{"text": text or ""}]})        
        return AgentResponse(is_final=True, text=text or "", data={})

    def set_runtime_options(self, options: Dict[str, Any]) -> None:
        self._model_id_override = options.get("model_id")
        temp = options.get("temperature")
        try:
            self._temperature_override = float(temp) if temp is not None else None
        except Exception:
            self._temperature_override = None

    async def process_document(self, bucket: str, key: str, message: Optional[str] = None) -> Dict[str, Any]:
        """Process a document from S3 and prepare it for context injection."""
        try:
            # Process the file using the new file processor
            file_content = self._file_processor.process_s3_file(bucket, key)
            
            # Store the enhanced message with file content for the next process_message call
            if message is not None:
                self._pending_file_content = self._file_processor.inject_file_content_into_message(
                    message, file_content
                )
            else:
                # If no message provided, just store the file content
                self._pending_file_content = file_content.to_context_string()
            
            # Return structured response for WebSocket
            response = self._file_processor.process_document_for_response(bucket, key)
            
            self._logger.info(
                f"Processed document {file_content.filename} ({file_content.extension}), "
                f"type: {file_content.content_type}, size: {file_content.metadata.get('file_size', 0)} bytes"
            )
            
            return response
            
        except Exception as e:
            self._logger.error(f"Error processing document from S3: {str(e)}")
            # Fallback to old method if new processor fails
            try:
                doc = get_document_content_from_s3(bucket, key)
                return {
                    "document": {
                        "name": doc.name,
                        "format": doc.format,
                        "source": {"bytes": doc.bytes_data.decode("utf-8", errors="ignore")},
                    }
                }
            except Exception as fallback_error:
                self._logger.error(f"Fallback also failed: {str(fallback_error)}")
                return {
                    "document": {
                        "name": Path(key).name,
                        "format": "error",
                        "error": str(e)
                    }
                }

    def get_recent_messages(self) -> list[dict]:
        # Provide last few turns for guardrail context
        return self._messages[-5:]
    
    def _create_tool_executor(self):
        """Create a custom tool executor that handles JWT token management."""
        
        class ToolExecutor:
            def __init__(self, agent):
                self.agent = agent
            
            async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
                self.agent._logger.info(f"🔧 Executing tool: {tool_name}")
                
                # Note: Memory management is no longer exposed as tools to the LLM
                # It's handled automatically when tools specify result_variable_name
                
                # Send progress update based on tool type
                if tool_name.startswith("get_"):
                    await self.agent._send_progress(f"Retrieving {tool_name.replace('get_', '').replace('_', ' ')} data...")
                elif tool_name.startswith("send_"):
                    await self.agent._send_progress(f"Sending {tool_name.replace('send_', '').replace('_', ' ')}...")
                else:
                    await self.agent._send_progress(f"Executing {tool_name}...")
                
                # The memory manager will handle result storage automatically
                
                # Check if this tool requires JWT authentication (from intelycx-core server)
                # We determine this by checking which server provides the tool
                tool_server = await self.agent._get_tool_server(tool_name)
                
                if tool_server == "intelycx-core":
                    # Special handling for login tool - it generates JWT tokens, doesn't need one
                    if tool_name == "intelycx_login":
                        result = await self.agent._mcp_manager.execute_tool(tool_name, arguments)
                    else:
                        # All other intelycx-core tools require JWT authentication
                        if not self.agent._intelycx_jwt_token:
                            return {
                                "error": "Manufacturing data access is currently unavailable due to authentication issues. Please check system configuration."
                            }
                        
                        # Inject JWT token into arguments
                        arguments_with_token = arguments.copy()
                        arguments_with_token["jwt_token"] = self.agent._intelycx_jwt_token
                        self.agent._logger.info(f"🔑 Injected JWT token for tool: {tool_name}")
                        
                        result = await self.agent._mcp_manager.execute_tool(tool_name, arguments_with_token)
                    
                    # Handle successful login - store JWT token
                    if tool_name == "intelycx_login" and isinstance(result, dict) and result.get("success"):
                        self.agent._intelycx_jwt_token = result.get("jwt_token")
                        self.agent._intelycx_user = result.get("user")
                        self.agent._logger.info(f"✅ Stored JWT token for user: {self.agent._intelycx_user}")
                    
                    # Check if token expired and try to re-authenticate (for non-login tools)
                    if tool_name != "intelycx_login" and isinstance(result, dict) and "error" in result and result["error"]:
                        error_msg = str(result["error"]).lower()
                        if "authentication failed" in error_msg or "token" in error_msg and "expired" in error_msg:
                            self.agent._logger.warning("🔑 JWT token expired, attempting re-authentication...")
                            try:
                                # Try to re-authenticate using environment credentials
                                username = os.environ.get("INTELYCX_CORE_USERNAME")
                                password = os.environ.get("INTELYCX_CORE_PASSWORD")
                                
                                if username and password:
                                    auth_result = await self.agent._mcp_manager.execute_tool("intelycx_login", {
                                        "username": username,
                                        "password": password
                                    })
                                    if auth_result.get("success"):
                                        self.agent._intelycx_jwt_token = auth_result.get("jwt_token")
                                        self.agent._logger.info("✅ Re-authentication successful, retrying tool call...")
                                        
                                        # Retry the original tool call with new token
                                        arguments_with_token["jwt_token"] = self.agent._intelycx_jwt_token
                                        result = await self.agent._mcp_manager.execute_tool(tool_name, arguments_with_token)
                                    else:
                                        self.agent._intelycx_jwt_token = None
                                        self.agent._intelycx_user = None
                                        return {
                                            "error": "Authentication token expired and re-authentication failed. Manufacturing data is temporarily unavailable."
                                        }
                                else:
                                    self.agent._intelycx_jwt_token = None
                                    self.agent._intelycx_user = None
                                    return {
                                        "error": "Authentication token expired and credentials not available for re-authentication."
                                    }
                            except Exception as e:
                                self.agent._logger.error(f"❌ Re-authentication error: {str(e)}")
                                self.agent._intelycx_jwt_token = None
                                self.agent._intelycx_user = None
                                return {
                                    "error": "Authentication token expired and re-authentication failed. Manufacturing data is temporarily unavailable."
                                }
                    
                    # Let memory manager handle the result
                    return await self.agent._memory.handle_tool_result(tool_name, arguments, result)
                
                # For all other tools (email, etc.), use normal execution
                result = await self.agent._mcp_manager.execute_tool(tool_name, arguments)
                
                # Let memory manager handle the result
                return await self.agent._memory.handle_tool_result(tool_name, arguments, result)
        
        return ToolExecutor(self)
    
    async def _get_tool_server(self, tool_name: str) -> Optional[str]:
        """Dynamically determine which server provides a specific tool."""
        try:
            discovered_tools = await self._mcp_manager.list_tools()
            for tool in discovered_tools:
                if tool["name"] == tool_name:
                    return tool["server"]
        except Exception as e:
            self._logger.error(f"Error getting tool server for {tool_name}: {str(e)}")
        return None

    # Memory management tools removed - memory is now handled internally
    # The SessionMemoryManager automatically stores tool results when
    # 'result_variable_name' is provided in tool arguments
    



