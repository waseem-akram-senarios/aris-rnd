from .base import BaseAgent, AgentResponse
from typing import Any, Dict, Optional, List, Callable, Awaitable
from pathlib import Path
from ..core.files import FileProcessor, get_document_content_from_s3
from ..llm.bedrock import BedrockClient
from ..database import init_database, close_database, DatabasePlanManager, DatabaseSessionMemoryManager, UnifiedPlanManager
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
        
        # Current chat ID for this session
        self._chat_id: Optional[str] = None
        
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
        
        # Initialize database memory manager (will be set when chat_id is available)
        self._memory = None  # Will be initialized in set_chat_id with actual chat_id
        self._db_plan_manager = None  # Database plan manager
        
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
        self._executioner = AgentExecutioner(self._mcp_manager, self._memory, plan_manager, self._bedrock, self._logger)
        # Set progress callback on executioner
        if hasattr(self, '_progress_callback') and self._progress_callback:
            self._executioner.set_progress_callback(self._progress_callback)
        # Set chat_id on executioner if we have one
        if self._chat_id:
            self._executioner.set_chat_id(self._chat_id)
    
    def set_plan_update_callback(self, callback: Optional[Callable[[ExecutionPlan], Awaitable[None]]]) -> None:
        """Set a callback function to send plan updates (legacy support)."""
        self._plan_update_callback = callback
        # Also set it on the executioner if it exists
        if self._executioner:
            self._executioner.set_plan_update_callback(callback)
    
    def set_chat_id(self, chat_id: str) -> None:
        """Set the current chat ID for this session and initialize database managers."""
        self._chat_id = chat_id
        self._logger.info(f"Set chat_id: {chat_id}")
        
        # Initialize database-backed memory manager and unified plan manager
        self._memory = DatabaseSessionMemoryManager(chat_id)
        self._unified_plan_manager = UnifiedPlanManager(chat_id)
        self._logger.info(f"🗄️ Initialized database managers for chat {chat_id}")
        
        # Set WebSocket callback for plan notifications
        if self._plan_manager:
            self._unified_plan_manager.set_websocket_callback(self._send_websocket_plan_notification)
        
        # Reinitialize executioner with new memory manager and unified plan manager
        if self._plan_manager:
            self._executioner = AgentExecutioner(self._mcp_manager, self._memory, self._unified_plan_manager, self._bedrock, self._logger)
            # Set callbacks and chat_id
            if hasattr(self, '_progress_callback') and self._progress_callback:
                self._executioner.set_progress_callback(self._progress_callback)
            self._executioner.set_chat_id(chat_id)
            self._logger.info(f"🔧 Reinitialized executioner with database memory manager")
        elif hasattr(self, '_executioner') and self._executioner:
            # Fallback: just set chat_id if executioner already exists
            self._executioner.set_chat_id(chat_id)
    
    async def update_chat_info(
        self, 
        user_id: str, 
        model_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update chat information in the database."""
        # Store chat info in database
        if self._memory:
            await self._memory.update_chat_info(
                user_id=user_id,
                agent_type="manufacturing", 
                model_id=model_id,
                metadata=metadata
            )
    
    async def _send_websocket_plan_notification(self, message_type: str, plan_data: Dict[str, Any]) -> None:
        """Send plan notification via WebSocket callback."""
        if self._plan_manager:
            try:
                # The WebSocket PlanManager expects ExecutionPlan objects, not dicts
                # We need to get the ExecutionPlan from the unified plan manager
                plan_id = plan_data.get("plan_id")
                if plan_id and self._unified_plan_manager:
                    execution_plan = await self._unified_plan_manager.get_plan(plan_id)
                    if execution_plan:
                        if message_type == "plan_create":
                            await self._plan_manager.create_plan(execution_plan)
                        elif message_type == "plan_update":
                            await self._plan_manager.update_plan(execution_plan)
                        self._logger.debug(f"📤 Sent {message_type} notification via WebSocket")
                    else:
                        self._logger.warning(f"Could not retrieve plan {plan_id} from database for WebSocket notification")
                else:
                    self._logger.warning(f"Missing plan_id or unified_plan_manager for {message_type} notification")
            except Exception as e:
                self._logger.warning(f"Failed to send {message_type} notification: {e}")

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
                    conversation_context=self._messages[-5:] if self._messages else None,
                    chat_id=self._chat_id
                )
                
                # Set current plan and notify UI FIRST (before database operations)
                self._current_plan = execution_plan  # For backward compatibility
                
                # DATABASE-FIRST: Store execution plan in database BEFORE any UI notifications or execution
                try:
                    # CRITICAL: Store in database first - execution CANNOT proceed if this fails
                    if self._unified_plan_manager:
                        await self._unified_plan_manager.create_plan(execution_plan)
                        self._logger.info(f"✅ Plan {execution_plan.plan_id} stored in database with {len(execution_plan.actions)} actions")
                    else:
                        raise Exception("UnifiedPlanManager not initialized - cannot proceed without database storage")
                    
                    # Store in memory for backward compatibility (non-critical)
                    try:
                        await self._memory.store("current_execution_plan", execution_plan, tool_name="planner")
                    except Exception as e:
                        self._logger.warning(f"⚠️ Failed to store execution plan in memory (non-critical): {e}")
                    
                    self._logger.info(f"📋 Created execution plan with {len(execution_plan.actions)} actions")
                    
                except Exception as e:
                    self._logger.error(f"❌ CRITICAL: Failed to store execution plan in database: {e}")
                    self._logger.error(f"❌ EXECUTION HALTED - Database storage is required")
                    # Return error response immediately - DO NOT PROCEED
                    return AgentResponse(
                        is_final=True,
                        text="I encountered a critical error while creating the execution plan. Please try again or contact support if the problem persists.",
                        data={}
                    )
                
            except Exception as e:
                self._logger.error(f"❌ Planning phase failed: {str(e)}")
                # Continue without planning if it fails
        else:
            # Use existing plan from plan manager or fallback to instance variable
            if self._plan_manager:
                execution_plan = self._plan_manager.get_current_plan()
            else:
                execution_plan = self._current_plan
        
        # Initialize tool_results variable
        tool_results = []
        
        # Now initialize only the MCP servers that are actually needed based on the plan
        tools = await self._initialize_required_servers_and_get_tools(execution_plan if 'execution_plan' in locals() else None)
        
        self._logger.info(f"🎯 TOTAL TOOLS AVAILABLE: {len(tools)}")
        self._logger.info(f"🔍 DEBUG: About to create system prompt, tool_results length: {len(tool_results)}")
        
        # Create system prompt based on tool availability
        if tools:
            auth_status = ""
            if self._intelycx_jwt_token:
                auth_status = " You are authenticated and ready to access Intelycx Core manufacturing data."
            else:
                auth_status = " Manufacturing data access is currently unavailable due to authentication issues."
            
            self._logger.info(f"🔍 DEBUG: Creating initial system prompt")
            
            # Add tool completion context if available
            tool_completion_context = ""
            if tool_results:
                # Create detailed context about completed actions
                completed_actions = []
                for tr in tool_results:
                    action_name = tr['action_name']
                    result = tr['result']
                    
                    # Add specific details based on tool type
                    if tr['tool_name'] == 'create_pdf' and isinstance(result, dict):
                        file_url = result.get('file_url', '')
                        file_name = result.get('file_name', 'document')
                        completed_actions.append(f"✅ {action_name}: Created '{file_name}' (Download: {file_url})")
                    elif tr['tool_name'] == 'get_fake_data' and isinstance(result, dict):
                        data_count = len(str(result)) if result else 0
                        completed_actions.append(f"✅ {action_name}: Retrieved {data_count} chars of manufacturing data")
                    elif tr['tool_name'] == 'intelycx_login' and isinstance(result, dict):
                        success = result.get('success', False)
                        user = result.get('user', 'Unknown')
                        completed_actions.append(f"✅ {action_name}: Authentication {'successful' if success else 'failed'} for {user}")
                    else:
                        completed_actions.append(f"✅ {action_name}: Completed successfully")
                
                tool_completion_context = f" EXECUTION RESULTS: I have completed these actions: {' | '.join(completed_actions)}. I should acknowledge these completed actions in my response and provide relevant details like download links. I should NOT call any tools again since they were already executed."
            
            # Add error context if plan has failures (will be set later)
            plan_error_context = ""
            
            system_prompt = f"You are ARIS, a helpful manufacturing assistant with access to production data tools, email capabilities, and session memory management. You can query machine information, machine group details, production summaries, and send email notifications.{auth_status} ALWAYS use the available tools when users ask about machines, production lines, manufacturing metrics, or need to send emails/notifications. Never make up or guess information - only provide data from actual tool calls. You have session memory capabilities - when retrieving data, you can store it in variables using the 'result_variable_name' parameter for later reference. Use memory management tools to list, retrieve, or clear stored variables as needed. Maintain context across the conversation and remember user-provided details such as their name during this session. When documents are provided, analyze them and answer questions based on their content.{tool_completion_context}{plan_error_context}"
        else:
            system_prompt = "You are ARIS, a helpful manufacturing assistant. Currently, I don't have access to production data tools or email capabilities, so I cannot provide specific information about machines, machine groups, production metrics, or send notifications. Please let the user know that the tools are temporarily unavailable and suggest they try again later. Never make up or fabricate manufacturing data. Be honest about your limitations."
        
        # Use the enhanced converse method with tools
        self._logger.info(f"🔍 DEBUG: About to send 'Executing plan...' progress message")
        await self._send_progress("Executing plan...")
        self._logger.info(f"🔍 DEBUG: Sent 'Executing plan...' progress message")
        
        # Execute the plan using the executioner (handles tool_call, analysis, response actions)
        if execution_plan and self._executioner:
            try:
                # Store original message count to identify new tool result messages
                original_message_count = len(self._messages)
                
                await self._executioner.execute_plan(execution_plan)
                self._logger.info(f"✅ Executioner completed plan {execution_plan.plan_id}")
                
                # Collect tool execution results from session memory
                tool_results = await self._collect_tool_results_from_plan(execution_plan)
                
                # Debug: Log what we found
                self._logger.info(f"🔍 Found {len(tool_results)} tool results in memory")
                for tr in tool_results:
                    self._logger.info(f"🔍 Tool result: {tr['tool_name']} -> {type(tr['result'])}")
                
                # Log tool results for debugging but don't inject into conversation
                if tool_results:
                    self._logger.info(f"📋 Found {len(tool_results)} completed tool executions")
                    for tr in tool_results:
                        self._logger.info(f"📋 Tool completed: {tr['tool_name']} -> {tr['action_name']}")
                else:
                    self._logger.warning("⚠️ No tool results found")
                    
            except Exception as e:
                self._logger.error(f"❌ Executioner failed: {str(e)}")
                # Continue to LLM even if executioner fails
            
        # Always collect tool results, even if execution partially failed
        if not tool_results and execution_plan:
            tool_results = await self._collect_tool_results_from_plan(execution_plan)
            self._logger.info(f"🔍 Collected {len(tool_results)} tool results after execution (including partial results)")
            
        # Update error context if plan failed
        if execution_plan and execution_plan.has_failed_actions():
            failed_actions = [a for a in execution_plan.actions if a.status == "failed"]
            error_context = f" NOTE: Some planned actions failed: {[a.name for a in failed_actions]}. Address these failures in your response and suggest alternatives if possible."
            # Update the system prompt with error context
            if tools:
                system_prompt = system_prompt.replace(plan_error_context, error_context)
            self._logger.info(f"⚠️ Plan has {len(failed_actions)} failed actions, updated system prompt")
        
        # Mark analysis and response actions as in_progress before LLM call
        if execution_plan:
            for action in execution_plan.actions:
                if action.type.value in ["analysis", "response"] and action.status == "starting":
                    execution_plan.update_action_status(action.id, "in_progress")
                    if self._plan_manager:
                        await self._plan_manager.update_plan(execution_plan)
                    icon = "🧠" if action.type.value == "analysis" else "💬"
                    self._logger.info(f"{icon} Starting {action.type.value}: {action.name}")

        # Use the base system prompt (tool results are now in conversation history)
        final_system_prompt = system_prompt
        self._logger.info(f"🔍 Using system prompt length: {len(final_system_prompt)} chars")

        # The executioner should have completed all actions including response generation
        # Get the final response from the response action result
        final_response_text = ""
        
        if execution_plan:
            # Find the response action and get its result
            for action in execution_plan.actions:
                if action.type.value == "response" and action.status == "completed":
                    response_result_key = f"tool_result_{action.id}"
                    response_result = await self._memory.get(response_result_key)
                    if response_result and isinstance(response_result, dict):
                        final_response_text = response_result.get("response_text", "")
                        self._logger.info(f"📝 Retrieved response from executioner: {len(final_response_text)} chars")
                        break
            
            self._logger.info(f"📋 Final plan status: {execution_plan.status}")

        # If no response was generated by the executioner, create a fallback
        if not final_response_text:
            if execution_plan and execution_plan.has_failed_actions():
                failed_actions = [a.name for a in execution_plan.actions if a.status == "failed"]
                final_response_text = f"I encountered some issues while processing your request. The following actions failed: {', '.join(failed_actions)}. Please try again or contact support if the problem persists."
            else:
                final_response_text = "I've completed processing your request. Please check the results above."
            
            self._logger.warning(f"⚠️ Using fallback response text: {len(final_response_text)} chars")

        # Collect tool results for structured data response
        if not tool_results and execution_plan:
            tool_results = await self._collect_tool_results_from_plan(execution_plan)
            self._logger.info(f"🔍 Collected {len(tool_results)} tool results for structured data")
        
        response_data = {}
        if tool_results:
            response_data = await self._create_structured_response_data(tool_results)
            self._logger.info(f"🔍 Created structured response data with {len(response_data)} sections")
            if "files" in response_data:
                self._logger.info(f"🔍 Response includes {len(response_data['files'])} files")
        else:
            self._logger.warning("⚠️ No tool results available for structured response data")

        # Append assistant reply to memory
        self._messages.append({"role": "assistant", "content": [{"text": final_response_text}]})        
        return AgentResponse(is_final=True, text=final_response_text, data=response_data)

    def set_runtime_options(self, options: Dict[str, Any]) -> None:
        # Validate and map model IDs to supported Bedrock models
        requested_model = options.get("model_id")
        self._model_id_override = self._validate_and_map_model_id(requested_model)
        
        temp = options.get("temperature")
        try:
            self._temperature_override = float(temp) if temp is not None else None
        except Exception:
            self._temperature_override = None
    
    def _validate_and_map_model_id(self, requested_model: Optional[str]) -> Optional[str]:
        """Validate and map client model IDs to supported Bedrock models."""
        if not requested_model:
            return None
        
        # Mapping of common client model names to Bedrock model IDs
        model_mapping = {
            # OpenAI models → Claude equivalents
            "gpt-4.1": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            "gpt-4": "us.anthropic.claude-3-7-sonnet-20250219-v1:0", 
            "gpt-4-turbo": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            "gpt-3.5-turbo": "us.anthropic.claude-3-7-haiku-20250219-v1:0",
            
            # Claude models (pass through if valid)
            "us.anthropic.claude-3-7-sonnet-20250219-v1:0": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            "us.anthropic.claude-3-7-haiku-20250219-v1:0": "us.anthropic.claude-3-7-haiku-20250219-v1:0",
            
            # Fallback mapping
            "claude-3-sonnet": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
            "claude-3-haiku": "us.anthropic.claude-3-7-haiku-20250219-v1:0",
        }
        
        mapped_model = model_mapping.get(requested_model)
        if mapped_model:
            if mapped_model != requested_model:
                self._logger.info(f"🔄 Mapped model '{requested_model}' → '{mapped_model}'")
            return mapped_model
        else:
            # Unknown model - log warning and use default
            self._logger.warning(f"⚠️ Unknown model '{requested_model}', using default Claude Sonnet")
            return "us.anthropic.claude-3-7-sonnet-20250219-v1:0"

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
                
                # Find the action ID from the current plan
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
                
                # Create plan context for centralized status updates
                plan_context = None
                if current_plan and action_id:
                    plan_context = {
                        "plan": current_plan,
                        "action_id": action_id,
                        "plan_manager": self.agent._plan_manager,
                        "logger": self.agent._logger
                    }
                else:
                    # Generate fallback ID for logging purposes
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
                
                # Note: Plan status updates are now handled centrally by MCP Manager
                
                # The memory manager will handle result storage automatically
                
                # Check if this tool requires JWT authentication (from intelycx-core server)
                # We determine this by checking which server provides the tool
                tool_server = await self.agent._get_tool_server(tool_name)
                
                if tool_server == "intelycx-core":
                    # Special handling for login tool - it generates JWT tokens, doesn't need one
                    if tool_name == "intelycx_login":
                        result = await self.agent._mcp_manager.execute_tool(tool_name, arguments, plan_context)
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
                        
                        result = await self.agent._mcp_manager.execute_tool(tool_name, arguments_with_token, plan_context)
                    
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
                                    }, plan_context)
                                    if auth_result.get("success"):
                                        self.agent._intelycx_jwt_token = auth_result.get("jwt_token")
                                        self.agent._logger.info("✅ Re-authentication successful, retrying tool call...")
                                        
                                        # Retry the original tool call with new token
                                        arguments_with_token["jwt_token"] = self.agent._intelycx_jwt_token
                                        result = await self.agent._mcp_manager.execute_tool(tool_name, arguments_with_token, plan_context)
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
                    return await self.agent._memory.handle_tool_result("unknown_action", tool_name, result, tool_name)
                
                # For all other tools (email, etc.), use normal execution
                try:
                    result = await self.agent._mcp_manager.execute_tool(tool_name, arguments, plan_context)
                    
                    # Note: Plan status updates are now handled centrally by MCP Manager
                    
                    # Determine final status for legacy CoT update
                    has_error = isinstance(result, dict) and result.get("error") and result["error"] != ""
                    final_status = "failed" if has_error else "completed"
                    
                    # Send legacy chain-of-thought update for backward compatibility
                    await self.agent._send_cot_update(ChainOfThoughtMessage(
                        action_id=action_id,
                        action_name=tool_name,
                        status=final_status,
                        message=f"Completed {tool_name}" if final_status == "completed" else f"Failed {tool_name}: {result.get('error', 'Unknown error')}",
                        details={"has_error": has_error}
                    ))
                    
                    # Let memory manager handle the result
                    return await self.agent._memory.handle_tool_result("unknown_action", tool_name, result, tool_name)
                    
                except Exception as e:
                    # Note: Plan status updates are now handled centrally by MCP Manager
                    
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
    
    async def _collect_tool_results_from_plan(self, execution_plan: ExecutionPlan) -> List[Dict[str, Any]]:
        """Collect tool execution results from the session memory based on the execution plan."""
        tool_results = []
        
        self._logger.info(f"🔍 Collecting tool results from plan with {len(execution_plan.actions)} actions")
        
        for action in execution_plan.actions:
            self._logger.info(f"🔍 Checking action: {action.name} (type: {action.type.value}, status: {action.status}, tool: {action.tool_name})")
            
            if action.type.value == "tool_call" and action.tool_name and action.status == "completed":
                # Look for stored results in memory using action ID or tool name
                result_keys = [
                    f"tool_result_{action.id}",
                    f"tool_result_{action.tool_name}",
                    action.tool_name,
                    f"{action.tool_name}_result"
                ]
                
                self._logger.info(f"🔍 Looking for tool result with keys: {result_keys}")
                
                for key in result_keys:
                    result = await self._memory.get(key)
                    if result:
                        self._logger.info(f"✅ Found tool result for {action.tool_name} with key: {key}")
                        tool_results.append({
                            "action_id": action.id,
                            "tool_name": action.tool_name,
                            "action_name": action.name,
                            "result": result
                        })
                        break
                else:
                    self._logger.warning(f"❌ No tool result found for {action.tool_name} (action: {action.id})")
        
        self._logger.info(f"🔍 Collected {len(tool_results)} total tool results")
        return tool_results
    
    def _create_tool_results_summary(self, tool_results: List[Dict[str, Any]]) -> str:
        """Create a summary of tool execution results for LLM context."""
        if not tool_results:
            return "No tool results available."
        
        summary_parts = []
        for tool_result in tool_results:
            self._logger.info(f"🔍 Processing tool result: {tool_result['tool_name']} -> {tool_result['result']}")
            tool_name = tool_result["tool_name"]
            action_name = tool_result["action_name"]
            result = tool_result["result"]
            
            # Create comprehensive summary for all tool types
            if isinstance(result, dict) and result.get("error"):
                # Handle error results
                error_msg = result.get("error", "Unknown error")
                summary_parts.append(f"❌ {action_name}: Failed - {error_msg}")
            elif isinstance(result, dict):
                # Handle successful results with structured data
                success_info = []
                
                # Common result fields to extract
                if "file_url" in result:
                    file_name = result.get("file_name", "file")
                    file_url = result.get("file_url", "")
                    success_info.append(f"File '{file_name}' created. Download: {file_url}")
                
                if "message" in result:
                    success_info.append(f"Message: {result['message']}")
                
                if "data" in result:
                    data = result["data"]
                    if isinstance(data, dict):
                        # Extract key information from data
                        if "count" in data:
                            success_info.append(f"Retrieved {data['count']} items")
                        elif "machines" in data:
                            success_info.append(f"Found {len(data['machines'])} machines")
                        elif "production" in data:
                            success_info.append("Production data retrieved")
                    elif isinstance(data, list):
                        success_info.append(f"Retrieved {len(data)} items")
                
                if "success" in result and result["success"]:
                    if tool_name == "send_email":
                        success_info.append("Email sent successfully")
                    elif tool_name == "intelycx_login":
                        user = result.get("user", "user")
                        success_info.append(f"Authenticated as {user}")
                
                # Generic success message if no specific info found
                if not success_info:
                    if "success" in result and result["success"]:
                        success_info.append("Operation completed successfully")
                    else:
                        success_info.append("Operation completed")
                
                summary_parts.append(f"✅ {action_name}: {' | '.join(success_info)}")
            else:
                # Handle simple/string results
                summary_parts.append(f"✅ {action_name}: {str(result)[:100]}...")
        
        return " | ".join(summary_parts)
    
    async def _create_structured_response_data(self, tool_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create structured response data for UI consumption based on tool results."""
        response_data = {}
        
        # Extract files from tool results (matching the expected UI format)
        files = []
        
        for tool_result in tool_results:
            tool_name = tool_result["tool_name"]
            result = tool_result["result"]
            
            if not isinstance(result, dict):
                continue
                
            # Handle file creation tools (PDF, Excel, Word, etc.)
            if "file_url" in result or "download_url" in result:
                # Try multiple possible filename fields
                filename = (
                    result.get("file_name") or 
                    result.get("filename") or 
                    result.get("name") or 
                    "document"
                )
                
                file_info = {
                    "name": filename,
                    "url": result.get("file_url") or result.get("download_url", "")
                }
                files.append(file_info)
                self._logger.info(f"🔍 Added file to response data: {file_info['name']} -> {file_info['url']}")
        
        # Only add files section if we have files
        if files:
            response_data["files"] = files
            
        return response_data
    
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
        
        # Add built-in memory tools first
        memory_tools = [
            {
                "toolSpec": {
                    "name": "search_memory",
                    "description": "Search session memory for previous tool results, files, and data",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "search_type": {
                                    "type": "string",
                                    "enum": ["files", "tool_results", "all"],
                                    "description": "Type of search to perform"
                                },
                                "tool_name": {
                                    "type": "string",
                                    "description": "Filter by specific tool name (optional)"
                                },
                                "tags": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Filter by tags (optional)"
                                }
                            }
                        }
                    }
                }
            },
            {
                "toolSpec": {
                    "name": "get_memory_item",
                    "description": "Get a specific memory item by key",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "key": {
                                    "type": "string",
                                    "description": "Memory key to retrieve"
                                }
                            },
                            "required": ["key"]
                        }
                    }
                }
            }
        ]
        
        tools.extend(memory_tools)
        self._logger.info(f"📋 Added {len(memory_tools)} built-in memory tools for planning")
        
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
            
            self._logger.info(f"📋 Discovered {len(discovered_tools)} MCP tools for planning via FastMCP")
            
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
                    elif action.tool_name in ["create_pdf"]:
                        required_servers.add("intelycx-file-generator")
        
        # If no plan or no tool calls identified, initialize all servers (fallback)
        if not required_servers:
            self._logger.info("🔧 No specific servers identified from plan, initializing all servers")
            required_servers = {"intelycx-core", "intelycx-email", "intelycx-file-generator"}
        
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
    



