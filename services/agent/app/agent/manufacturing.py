from .base import BaseAgent, AgentResponse
from typing import Any, Dict, Optional, List, Callable, Awaitable
from pathlib import Path
from ..core.files import FileProcessor, get_document_content_from_s3
from ..llm.bedrock import BedrockClient
from ..core.memory import SessionMemoryManager
from ..mcp import MCPServerManager
from ..config.settings import load_settings
from ..planning.planner import AgentPlanner
from ..planning.executioner import AgentExecutioner
from ..planning.observer import PlanManager
from ..planning import ExecutionPlan, ChainOfThoughtMessage, create_planning_websocket_message, create_plan_update_websocket_message
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
        
        # Planning callback for sending execution plans
        self._planning_callback: Optional[Callable[[ExecutionPlan], Awaitable[None]]] = None
        
        # Chain of thought callback for execution progress
        self._cot_callback: Optional[Callable[[ChainOfThoughtMessage], Awaitable[None]]] = None
        
        # Initialize session memory manager
        self._memory = SessionMemoryManager(
            auto_store_results=True,
            max_size_mb=50.0  # Reasonable limit for session memory
        )
        
        # Initialize planner, executioner, and plan manager
        self._planner = AgentPlanner(self._bedrock, self._logger)
        self._plan_manager: Optional[PlanManager] = None
        self._executioner: Optional[AgentExecutioner] = None
        
        # Current execution plan (for backward compatibility)
        self._current_plan: Optional[ExecutionPlan] = None

    def set_progress_callback(self, callback: Optional[Callable[[str], Awaitable[None]]]) -> None:
        """Set a callback function to send progress updates during processing."""
        self._progress_callback = callback

    def set_planning_callback(self, callback: Optional[Callable[[ExecutionPlan], Awaitable[None]]]) -> None:
        """Set a callback function to send execution plans."""
        self._planning_callback = callback

    def set_plan_manager(self, plan_manager: PlanManager) -> None:
        """Set the plan manager for handling plan lifecycle."""
        self._plan_manager = plan_manager
        # Initialize executioner with plan manager
        self._executioner = AgentExecutioner(self._mcp_manager, self._memory, plan_manager, self._logger)
        # Set progress callback on executioner
        if hasattr(self, '_progress_callback') and self._progress_callback:
            self._executioner.set_progress_callback(self._progress_callback)
    
    def set_plan_update_callback(self, callback: Optional[Callable[[ExecutionPlan], Awaitable[None]]]) -> None:
        """Set a callback function to send plan updates (legacy support)."""
        self._plan_update_callback = callback
        # Also set it on the executioner if it exists
        if self._executioner:
            self._executioner.set_plan_update_callback(callback)

    async def _send_progress(self, message: str) -> None:
        """Send a progress update if callback is available."""
        if self._progress_callback:
            try:
                await self._progress_callback(message)
            except Exception as e:
                self._logger.warning(f"Failed to send progress update: {e}")

    async def _send_plan(self, plan: ExecutionPlan) -> None:
        """Send an execution plan if callback is available."""
        if self._planning_callback:
            try:
                await self._planning_callback(plan)
            except Exception as e:
                self._logger.warning(f"Failed to send execution plan: {e}")

    async def _send_cot_update(self, cot_message: ChainOfThoughtMessage) -> None:
        """Send a chain-of-thought update if callback is available."""
        if self._cot_callback:
            try:
                await self._cot_callback(cot_message)
            except Exception as e:
                self._logger.warning(f"Failed to send chain-of-thought update: {e}")

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

        # Check if we need to create a new plan using plan manager
        should_create_new_plan = True
        if self._plan_manager:
            should_create_new_plan = self._plan_manager.should_create_new_plan()
            current_plan = self._plan_manager.get_current_plan()
            if current_plan and not should_create_new_plan:
                self._logger.info(f"⏳ Plan {current_plan.plan_id} is still active (status: {current_plan.status})")
            elif current_plan and should_create_new_plan:
                self._logger.info(f"✅ Previous plan {current_plan.plan_id} finished (status: {current_plan.status}), creating new plan")
        elif self._current_plan:
            # Fallback to old logic if no plan manager
            if self._current_plan.status in ["new", "in_progress"]:
                self._logger.info(f"⏳ Plan {self._current_plan.plan_id} is still active (status: {self._current_plan.status})")
                should_create_new_plan = False
            elif self._current_plan.status in ["completed", "error", "aborted"]:
                self._logger.info(f"✅ Previous plan {self._current_plan.plan_id} finished (status: {self._current_plan.status}), creating new plan")
                should_create_new_plan = True
        
        if should_create_new_plan:
            # PLANNING PHASE: Create execution plan FIRST (with basic tool discovery)
            await self._send_progress("Creating execution plan...")
            
            # Quick tool discovery for planning (without full initialization)
            basic_tools = await self._get_available_tools_for_planning()
            
            try:
                execution_plan = await self._planner.create_execution_plan(
                    user_query=enhanced_message,
                    available_tools=basic_tools,
                    conversation_context=self._messages[-5:] if self._messages else None
                )
                
                # Save the plan to session memory and notify observers
                self._current_plan = execution_plan  # For backward compatibility
                await self._memory.store("current_execution_plan", execution_plan, tool_name="planner")
                
                # Use plan manager to create plan (triggers observers automatically)
                if self._plan_manager:
                    await self._plan_manager.create_plan(execution_plan)
                else:
                    # Fallback to legacy callback
                    await self._send_plan(execution_plan)
                
                self._logger.info(f"📋 Created execution plan with {len(execution_plan.actions)} actions")
                
            except Exception as e:
                self._logger.error(f"❌ Planning phase failed: {str(e)}")
                # Continue without planning if it fails
        else:
            # Use existing plan from plan manager or fallback to instance variable
            if self._plan_manager:
                execution_plan = self._plan_manager.get_current_plan()
            else:
                execution_plan = self._current_plan
        
        # Now initialize only the MCP servers that are actually needed based on the plan
        tools = await self._initialize_required_servers_and_get_tools(execution_plan if 'execution_plan' in locals() else None)
        
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
        await self._send_progress("Executing plan...")
        
        # Use LLM with enhanced tool executor that updates plan status
        text = await self._bedrock.converse(
            model_id=model_id,
            messages=self._messages[-20:],
            tools=tools,
            tool_executor=self._create_tool_executor_with_cot(),
            system=[{"text": system_prompt}],
            temperature=temperature,
        )

        # Mark plan as completed after LLM finishes
        if self._plan_manager and execution_plan:
            execution_plan.auto_update_plan_status()
            if execution_plan.status != "completed" and not execution_plan.has_failed_actions():
                # If all actions are done but plan isn't marked completed, mark it now
                execution_plan.update_plan_status("completed")
            await self._plan_manager.update_plan(execution_plan)
            self._logger.info(f"📋 Final plan status: {execution_plan.status}")

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
    
    def _create_tool_executor_with_cot(self):
        """Create a custom tool executor that handles JWT token management and sends chain-of-thought updates."""
        
        class ToolExecutorWithCoT:
            def __init__(self, agent):
                self.agent = agent
            
            async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
                self.agent._logger.info(f"🔧 Executing tool: {tool_name}")
                
                # Find the action ID from the current plan and update status
                action_id = None
                current_plan = None
                
                # Get current plan from plan manager or fallback
                if self.agent._plan_manager:
                    current_plan = self.agent._plan_manager.get_current_plan()
                elif self.agent._current_plan:
                    current_plan = self.agent._current_plan
                
                if current_plan:
                    action = current_plan.get_action_by_tool_name(tool_name)
                    if action:
                        action_id = action.id
                        # Update action status via plan manager
                        if self.agent._plan_manager:
                            await self.agent._plan_manager.update_action_status(action_id, "starting")
                        else:
                            # Fallback: update directly
                            current_plan.update_action_status(action_id, "starting")
                
                # Fallback to generated ID if not found in plan
                if not action_id:
                    import uuid
                    action_id = str(uuid.uuid4())
                    self.agent._logger.warning(f"⚠️ Tool {tool_name} not found in current plan, using generated ID")
                
                # Send legacy progress update for backward compatibility
                await self.agent._send_cot_update(ChainOfThoughtMessage(
                    action_id=action_id,
                    action_name=tool_name,
                    status="starting",
                    message=f"Starting {tool_name}...",
                    details={"arguments": arguments}
                ))
                
                # Note: Memory management is no longer exposed as tools to the LLM
                # It's handled automatically when tools specify result_variable_name
                
                # Send progress update based on tool type (legacy support)
                if tool_name.startswith("get_"):
                    await self.agent._send_progress(f"Retrieving {tool_name.replace('get_', '').replace('_', ' ')} data...")
                elif tool_name.startswith("send_"):
                    await self.agent._send_progress(f"Sending {tool_name.replace('send_', '').replace('_', ' ')}...")
                else:
                    await self.agent._send_progress(f"Executing {tool_name}...")
                
                # Update action status to in_progress
                if current_plan and action_id:
                    if self.agent._plan_manager:
                        await self.agent._plan_manager.update_action_status(action_id, "in_progress")
                    else:
                        current_plan.update_action_status(action_id, "in_progress")
                
                # Send legacy chain-of-thought update for backward compatibility
                await self.agent._send_cot_update(ChainOfThoughtMessage(
                    action_id=action_id,
                    action_name=tool_name,
                    status="in_progress",
                    message=f"Executing {tool_name} with provided parameters..."
                ))
                
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
                    
                    # Update plan status: completed or failed
                    has_error = isinstance(result, dict) and result.get("error") and result["error"] != ""
                    final_status = "failed" if has_error else "completed"
                    if current_plan and action_id:
                        if self.agent._plan_manager:
                            await self.agent._plan_manager.update_action_status(action_id, final_status)
                        else:
                            current_plan.update_action_status(action_id, final_status)
                    
                    # Send legacy chain-of-thought update for backward compatibility
                    await self.agent._send_cot_update(ChainOfThoughtMessage(
                        action_id=action_id,
                        action_name=tool_name,
                        status=final_status,
                        message=f"Completed {tool_name}" if final_status == "completed" else f"Failed {tool_name}: {result.get('error', 'Unknown error')}",
                        details={"has_error": has_error}
                    ))
                    
                    # Let memory manager handle the result
                    return await self.agent._memory.handle_tool_result(tool_name, arguments, result)
                
                # For all other tools (email, etc.), use normal execution
                try:
                    result = await self.agent._mcp_manager.execute_tool(tool_name, arguments)
                    
                    # Update plan status: completed or failed
                    has_error = isinstance(result, dict) and result.get("error") and result["error"] != ""
                    final_status = "failed" if has_error else "completed"
                    if current_plan and action_id:
                        if self.agent._plan_manager:
                            await self.agent._plan_manager.update_action_status(action_id, final_status)
                        else:
                            current_plan.update_action_status(action_id, final_status)
                    
                    # Send legacy chain-of-thought update for backward compatibility
                    await self.agent._send_cot_update(ChainOfThoughtMessage(
                        action_id=action_id,
                        action_name=tool_name,
                        status=final_status,
                        message=f"Completed {tool_name}" if final_status == "completed" else f"Failed {tool_name}: {result.get('error', 'Unknown error')}",
                        details={"has_error": has_error}
                    ))
                    
                    # Let memory manager handle the result
                    return await self.agent._memory.handle_tool_result(tool_name, arguments, result)
                    
                except Exception as e:
                    # Update plan status: failed
                    if current_plan and action_id:
                        if self.agent._plan_manager:
                            await self.agent._plan_manager.update_action_status(action_id, "failed")
                        else:
                            current_plan.update_action_status(action_id, "failed")
                    
                    # Send legacy chain-of-thought update for backward compatibility
                    await self.agent._send_cot_update(ChainOfThoughtMessage(
                        action_id=action_id,
                        action_name=tool_name,
                        status="failed",
                        message=f"Failed {tool_name}: {str(e)}",
                        details={"error": str(e)}
                    ))
                    raise
        
        return ToolExecutorWithCoT(self)
    
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

    async def _get_available_tools_for_planning(self) -> List[Dict[str, Any]]:
        """Get available tools for planning using FastMCP client discovery."""
        # Initialize MCP servers if not already done (lightweight for planning)
        if not self._mcp_initialized:
            self._logger.info("🚀 Starting MCP servers for planning...")
            start_results = await self._mcp_manager.start_all_servers()
            self._logger.info(f"📊 MCP START RESULTS (planning): {start_results}")
            self._mcp_initialized = True
        
        # Use FastMCP client to discover available tools dynamically
        tools = []
        try:
            discovered_tools = await self._mcp_manager.list_tools()
            for tool in discovered_tools:
                # Convert MCP tool format to Bedrock tool format for planning
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
                self._logger.info(f"📋 Planning tool discovered: {tool['name']} from {tool['server']}")
            
            self._logger.info(f"📋 Discovered {len(tools)} tools for planning via FastMCP")
            
        except Exception as e:
            self._logger.error(f"❌ Error discovering tools for planning: {str(e)}")
            # Return empty list if discovery fails - planning can still work without tools
            self._logger.warning("⚠️ Planning will proceed without tool information")
        
        return tools

    async def _initialize_required_servers_and_get_tools(self, execution_plan: Optional[ExecutionPlan] = None) -> List[Dict[str, Any]]:
        """Initialize only the MCP servers needed based on the execution plan."""
        required_servers = set()
        
        # Analyze the execution plan to determine which servers are needed
        if execution_plan:
            for action in execution_plan.actions:
                if action.tool_name:
                    if action.tool_name in ["send_email"]:
                        required_servers.add("intelycx-email")
                    elif action.tool_name in ["get_machine", "get_machine_group", "get_production_summary", "get_fake_data"]:
                        required_servers.add("intelycx-core")
        
        # If no plan or no tool calls identified, initialize all servers (fallback)
        if not required_servers:
            self._logger.info("🔧 No specific servers identified from plan, initializing all servers")
            required_servers = {"intelycx-core", "intelycx-email"}
        
        self._logger.info(f"🎯 Initializing required servers: {required_servers}")
        
        # MCP servers should already be initialized from planning phase
        if not self._mcp_initialized:
            await self._send_progress("Initializing required systems...")
            self._logger.info("🚀 Starting required MCP servers (fallback)...")
            start_results = await self._mcp_manager.start_all_servers()
            self._logger.info(f"📊 MCP START RESULTS: {start_results}")
            self._mcp_initialized = True
        else:
            self._logger.info("🔗 MCP servers already initialized from planning phase")
        
        # Only authenticate with manufacturing systems if they're actually needed
        if "intelycx-core" in required_servers and not self._intelycx_jwt_token and "intelycx-core" in self._mcp_manager.connections:
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
        elif "intelycx-core" in required_servers and not self._intelycx_jwt_token:
            await self._send_progress("Manufacturing core system not available. Limited functionality...")
            self._logger.warning("⚠️ Intelycx Core server not connected - skipping authentication")
        elif "intelycx-core" not in required_servers:
            self._logger.info("🎯 Manufacturing systems not required for this request - skipping authentication")
        
        # Get available tools from the required MCP servers  
        await self._send_progress("Preparing execution environment...")
        tools = []
        self._logger.info(f"🔍 MCP SERVERS: Found {len(self._mcp_manager.servers)} configured servers")
        self._logger.info(f"🔗 MCP CONNECTIONS: {len(self._mcp_manager.connections)} active connections")
        
        # Dynamically discover tools from connected MCP servers
        try:
            discovered_tools = await self._mcp_manager.list_tools()
            for tool in discovered_tools:
                # Only include tools from required servers
                if tool["server"] in required_servers:
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
            
            self._logger.info(f"🎯 DISCOVERED {len(tools)} tools from required servers")
            
        except Exception as e:
            self._logger.error(f"❌ Error discovering tools from MCP servers: {str(e)}")
            # Fallback: no tools from MCP servers
            self._logger.warning("⚠️ Falling back to no MCP tools due to discovery error")
        
        return tools

    # Memory management tools removed - memory is now handled internally
    # The SessionMemoryManager automatically stores tool results when
    # 'result_variable_name' is provided in tool arguments
    



