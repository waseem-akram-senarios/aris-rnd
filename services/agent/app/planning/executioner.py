"""Agent executioner for executing planned actions."""

import logging
from typing import Dict, Any, Optional, Callable, Awaitable, TYPE_CHECKING

from .models import ExecutionPlan, PlannedAction, ChainOfThoughtMessage, create_plan_update_websocket_message
from ..mcp import MCPServerManager
from ..database.memory_manager import DatabaseSessionMemoryManager
from ..core.llm_tools import LLMTools

if TYPE_CHECKING:
    from .observer import PlanManager


class AgentExecutioner:
    """Executes planned actions and updates plan status."""
    
    def __init__(
        self, 
        mcp_manager: MCPServerManager, 
        memory: DatabaseSessionMemoryManager,
        plan_manager: Optional['PlanManager'] = None,
        bedrock_client = None,
        logger: Optional[logging.Logger] = None
    ):
        self.mcp_manager = mcp_manager
        self.memory = memory
        self.plan_manager = plan_manager
        self.logger = logger or logging.getLogger(__name__)
        
        # Initialize LLM tools if bedrock client is provided
        self.llm_tools = LLMTools(bedrock_client, memory, logger) if bedrock_client else None
        
        # Callbacks (for backward compatibility)
        self._plan_update_callback: Optional[Callable[[ExecutionPlan], Awaitable[None]]] = None
        self._progress_callback: Optional[Callable[[str], Awaitable[None]]] = None
        
        # Authentication state
        self._intelycx_jwt_token: Optional[str] = None
        self._intelycx_user: Optional[str] = None
        
        # Chat context
        self._chat_id: Optional[str] = None
    
    def set_plan_update_callback(self, callback: Optional[Callable[[ExecutionPlan], Awaitable[None]]]) -> None:
        """Set callback for sending plan updates."""
        self._plan_update_callback = callback
    
    def set_progress_callback(self, callback: Optional[Callable[[str], Awaitable[None]]]) -> None:
        """Set callback for sending progress updates."""
        self._progress_callback = callback
    
    def set_chat_id(self, chat_id: str) -> None:
        """Set the current chat ID for this session."""
        self._chat_id = chat_id
    
    async def _send_plan_update(self, plan: ExecutionPlan) -> None:
        """Send a plan update via plan manager or callback."""
        # Use plan manager if available (preferred)
        if self.plan_manager:
            await self.plan_manager.update_plan(plan)
        # Fall back to callback for backward compatibility
        elif self._plan_update_callback:
            try:
                await self._plan_update_callback(plan)
            except Exception as e:
                self.logger.warning(f"Failed to send plan update: {e}")
        else:
            self.logger.warning("No plan manager or callback available for plan updates")
    
    async def _send_progress(self, message: str) -> None:
        """Send a progress update if callback is available."""
        if self._progress_callback:
            try:
                await self._progress_callback(message)
            except Exception as e:
                self.logger.warning(f"Failed to send progress update: {e}")
    
    async def execute_plan(self, plan: ExecutionPlan) -> ExecutionPlan:
        """Execute the entire plan, updating action statuses as we go."""
        self.logger.info(f"🚀 Starting execution of plan {plan.plan_id}")
        
        try:
            # Mark plan as in progress in database
            plan.update_plan_status("in_progress")
            if self.plan_manager and hasattr(self.plan_manager, 'update_plan_status'):
                await self.plan_manager.update_plan_status(plan.plan_id, "in_progress")
            await self._send_plan_update(plan)
            
            # Execute actions in dependency order
            max_iterations = len(plan.actions) * 2  # Prevent infinite loops
            iteration = 0
            
            while iteration < max_iterations:
                executed_in_iteration = False
                iteration += 1
                
                for action in plan.actions:
                    # Only execute pending actions
                    if action.status != "pending":
                        continue
                        
                    # Check if dependencies are satisfied
                    if not self._are_dependencies_satisfied(plan, action):
                        continue
                    
                    # Execute based on action type
                    if action.type.value == "tool_call" and action.tool_name:
                        await self._execute_tool_action(plan, action)
                        executed_in_iteration = True
                        
                        # Stop execution if plan failed
                        if plan.status == "error":
                            self.logger.error(f"❌ Plan execution failed: {plan.plan_id}")
                            return plan
                            
                    elif action.type.value == "analysis":
                        # Execute analysis actions using built-in LLM tools
                        await self._execute_analysis_action(plan, action)
                        executed_in_iteration = True
                        
                    elif action.type.value == "response":
                        # Execute response actions using built-in LLM tools
                        await self._execute_response_action(plan, action)
                        executed_in_iteration = True
                
                # Auto-update plan status after each iteration
                plan.auto_update_plan_status()
                await self._send_plan_update(plan)
                
                # If no actions were executed, we're done or stuck
                if not executed_in_iteration:
                    break
            
            # Final status update in memory and database
            final_status = plan.auto_update_plan_status()
            if self.plan_manager and hasattr(self.plan_manager, 'update_plan_status'):
                await self.plan_manager.update_plan_status(plan.plan_id, final_status)
            await self._send_plan_update(plan)
            self.logger.info(f"✅ Completed execution of plan {plan.plan_id} with status: {final_status}")
            
        except Exception as e:
            # Mark plan as error if execution fails
            plan.update_plan_status("error")
            if self.plan_manager and hasattr(self.plan_manager, 'update_plan_status'):
                await self.plan_manager.update_plan_status(plan.plan_id, "error")
            await self._send_plan_update(plan)
            self.logger.error(f"❌ Plan execution error: {plan.plan_id} - {str(e)}")
            raise
        
        return plan
    
    async def _execute_tool_action(self, plan: ExecutionPlan, action: PlannedAction) -> None:
        """Execute a tool call action."""
        self.logger.info(f"🔧 Executing tool action: {action.tool_name}")
        
        # Resolve template variables in arguments using stored results
        resolved_arguments = await self._resolve_template_arguments(action.arguments or {}, plan)
        self.logger.info(f"🔧 Resolved arguments for {action.tool_name}: {len(str(resolved_arguments))} chars")
        
        # Create plan context for MCP manager
        plan_context = {
            "plan": plan,
            "action_id": action.id,
            "plan_manager": self.plan_manager,
            "logger": self.logger
        }
        
        try:
            # Execute the tool with plan context (MCP manager will handle all status updates)
            result = await self._execute_tool(action.tool_name, resolved_arguments, plan_context)
            
            # Store tool result in memory for LLM access
            await self.memory.store(
                key=f"tool_result_{action.id}",
                value=result,
                tool_name=action.tool_name,
                tags=["executioner_result", "tool_result"]
            )
            
            self.logger.info(f"✅ Completed tool action: {action.tool_name}")
            
        except Exception as e:
            self.logger.error(f"❌ Tool action failed: {action.tool_name} - {str(e)}")
            raise
    
    async def _resolve_template_arguments(self, arguments: Dict[str, Any], plan: ExecutionPlan) -> Dict[str, Any]:
        """Resolve template variables in tool arguments using stored memory results."""
        import re
        import json
        
        self.logger.info(f"🔧 Template resolution starting for arguments: {json.dumps(arguments, indent=2)}")
        
        resolved_args = {}
        
        for key, value in arguments.items():
            if isinstance(value, str) and "{{" in value and "}}" in value:
                # Find template variables like {{action_id.result.field}}
                template_pattern = r'\{\{([^}]+)\}\}'
                matches = re.findall(template_pattern, value)
                
                resolved_value = value
                self.logger.info(f"🔧 Template resolution for '{key}': found {len(matches)} variables in '{value}'")
                
                for match in matches:
                    self.logger.info(f"🔧 Processing template variable: {match}")
                    # Parse the template variable (e.g., "c3d4e5f6-a7b8-9012-cdef-123456789012.result")
                    parts = match.split('.')
                    if len(parts) >= 2:
                        action_ref = parts[0]
                        field_path = parts[1:]
                        
                        # Look for stored result by action ID (try both fake and real IDs)
                        result_key = f"tool_result_{action_ref}"
                        stored_result = await self.memory.get(result_key)
                        
                        # If not found with fake ID, try to find by dependency relationship and template context
                        if not stored_result:
                            # For analysis templates (like c3d4e5f6-a7b8-9012-cdef-345678901234.result), 
                            # look specifically for analysis actions
                            if field_path == ["result"]:
                                # Look for analysis actions first
                                for action in plan.actions:
                                    if action.status == "completed" and action.type.value == "analysis":
                                        real_result_key = f"tool_result_{action.id}"
                                        candidate_result = await self.memory.get(real_result_key)
                                        if candidate_result:
                                            stored_result = candidate_result
                                            result_key = real_result_key
                                            self.logger.info(f"🔧 Mapped analysis template {action_ref} -> real action {action.id} (analysis)")
                                            break
                            
                            # If still not found, try to find the most relevant completed action
                            if not stored_result:
                                # For data-related templates, prioritize data-generating tools
                                data_tools = ["create_pdf", "get_fake_data", "get_machine", "get_production_summary"]
                                
                                # For file URLs, prioritize create_pdf actions
                                if "file_url" in field_path or "url" in field_path:
                                    for action in plan.actions:
                                        if (action.status == "completed" and 
                                            action.type.value == "tool_call" and 
                                            action.tool_name == "create_pdf"):
                                            real_result_key = f"tool_result_{action.id}"
                                            candidate_result = await self.memory.get(real_result_key)
                                            if candidate_result:
                                                stored_result = candidate_result
                                                result_key = real_result_key
                                                self.logger.info(f"🔧 Mapped file URL template {action_ref} -> PDF action {action.id}")
                                                break
                                
                                # Then try other data-generating tools
                                if not stored_result:
                                    for action in plan.actions:
                                        if (action.status == "completed" and 
                                            action.type.value == "tool_call" and 
                                            action.tool_name in data_tools):
                                            real_result_key = f"tool_result_{action.id}"
                                            candidate_result = await self.memory.get(real_result_key)
                                            if candidate_result:
                                                stored_result = candidate_result
                                                result_key = real_result_key
                                                self.logger.info(f"🔧 Mapped template {action_ref} -> real action {action.id} ({action.tool_name}) [data tool]")
                                                break
                                
                                # If still not found, try any completed action as fallback
                                if not stored_result:
                                    for action in plan.actions:
                                        if action.status == "completed" and action.type.value in ["tool_call", "analysis"]:
                                            real_result_key = f"tool_result_{action.id}"
                                            candidate_result = await self.memory.get(real_result_key)
                                            if candidate_result:
                                                stored_result = candidate_result
                                                result_key = real_result_key
                                                self.logger.info(f"🔧 Mapped template {action_ref} -> real action {action.id} ({action.type.value}) [fallback]")
                                                break
                        
                        if stored_result:
                            # Navigate through the field path
                            current_value = stored_result
                            for field in field_path:
                                if isinstance(current_value, dict) and field in current_value:
                                    current_value = current_value[field]
                                else:
                                    current_value = None
                                    break
                            
                            if current_value is not None:
                                # Convert to string if it's a complex object
                                if isinstance(current_value, (dict, list)):
                                    replacement = json.dumps(current_value, indent=2)
                                else:
                                    replacement = str(current_value)
                                
                                resolved_value = resolved_value.replace(f"{{{{{match}}}}}", replacement)
                                self.logger.info(f"🔧 Resolved template {{{{ {match} }}}} -> {len(replacement)} chars")
                            else:
                                # Special case: if looking for .result and this is an analysis action, try formatted_content
                                if field_path == ["result"] and isinstance(stored_result, dict) and "formatted_content" in stored_result:
                                    replacement = stored_result["formatted_content"]
                                    resolved_value = resolved_value.replace(f"{{{{{match}}}}}", replacement)
                                    self.logger.info(f"🔧 Resolved template {{{{ {match} }}}} -> analysis formatted_content ({len(replacement)} chars)")
                                # Special case: if looking for .result on data tools, serialize the entire result as JSON
                                elif field_path == ["result"] and isinstance(stored_result, dict):
                                    # For data tools like get_fake_data, serialize the entire result
                                    replacement = json.dumps(stored_result, indent=2)
                                    resolved_value = resolved_value.replace(f"{{{{{match}}}}}", replacement)
                                    self.logger.info(f"🔧 Resolved template {{{{ {match} }}}} -> full data result ({len(replacement)} chars)")
                                else:
                                    self.logger.warning(f"⚠️ Could not resolve template variable: {match}")
                                    self.logger.warning(f"⚠️ Available fields in result: {list(stored_result.keys()) if isinstance(stored_result, dict) else 'not a dict'}")
                        else:
                            self.logger.warning(f"⚠️ No stored result found for action: {action_ref}")
                
                resolved_args[key] = resolved_value
            elif isinstance(value, dict):
                # Recursively resolve nested dictionaries
                resolved_args[key] = await self._resolve_template_arguments(value, plan)
            elif isinstance(value, list):
                # Recursively resolve lists
                resolved_list = []
                for item in value:
                    if isinstance(item, str) and "{{" in item and "}}" in item:
                        # Resolve template in list item
                        template_pattern = r'\{\{([^}]+)\}\}'
                        matches = re.findall(template_pattern, item)
                        resolved_item = item
                        
                        for match in matches:
                            self.logger.info(f"🔧 Processing list template variable: {match}")
                            parts = match.split('.')
                            if len(parts) >= 2:
                                action_ref = parts[0]
                                field_path = parts[1:]
                                
                                # Look for stored result by action ID
                                result_key = f"tool_result_{action_ref}"
                                stored_result = await self.memory.get(result_key)
                                
                                # If not found, try to find by tool type (prioritize create_pdf for file URLs)
                                if not stored_result and "file_url" in field_path:
                                    for action in plan.actions:
                                        if (action.status == "completed" and 
                                            action.type.value == "tool_call" and 
                                            action.tool_name == "create_pdf"):
                                            real_result_key = f"tool_result_{action.id}"
                                            candidate_result = await self.memory.get(real_result_key)
                                            if candidate_result:
                                                stored_result = candidate_result
                                                self.logger.info(f"🔧 Mapped list template {action_ref} -> PDF action {action.id}")
                                                break
                                
                                if stored_result:
                                    # Navigate through the field path
                                    current_value = stored_result
                                    for field in field_path:
                                        if isinstance(current_value, dict) and field in current_value:
                                            current_value = current_value[field]
                                        else:
                                            current_value = None
                                            break
                                    
                                    if current_value is not None:
                                        replacement = str(current_value)
                                        resolved_item = resolved_item.replace(f"{{{{{match}}}}}", replacement)
                                        self.logger.info(f"🔧 Resolved list template {{{{{match}}}}} -> {replacement}")
                                    else:
                                        # Special case: if looking for .result on data tools, serialize the entire result
                                        if field_path == ["result"] and isinstance(stored_result, dict):
                                            replacement = json.dumps(stored_result, indent=2)
                                            resolved_item = resolved_item.replace(f"{{{{{match}}}}}", replacement)
                                            self.logger.info(f"🔧 Resolved list template {{{{{match}}}}} -> full data result ({len(replacement)} chars)")
                                        else:
                                            self.logger.warning(f"⚠️ Could not resolve list template variable: {match}")
                        
                        resolved_list.append(resolved_item)
                    elif isinstance(item, dict):
                        resolved_list.append(await self._resolve_template_arguments(item, plan))
                    else:
                        resolved_list.append(item)
                resolved_args[key] = resolved_list
            else:
                resolved_args[key] = value
        
        return resolved_args
    
    def _are_dependencies_satisfied(self, plan: ExecutionPlan, action: PlannedAction) -> bool:
        """Check if all dependencies for an action are satisfied."""
        if not action.depends_on:
            return True  # No dependencies
        
        for dep_id in action.depends_on:
            # Find the dependent action
            dep_action = None
            for a in plan.actions:
                if a.id == dep_id:
                    dep_action = a
                    break
            
            if not dep_action:
                self.logger.warning(f"⚠️ Dependency not found: {dep_id} for action {action.name}")
                return False
            
            # Check if dependency is completed
            if dep_action.status not in ["completed"]:
                self.logger.info(f"🔄 Action '{action.name}' waiting for dependency '{dep_action.name}' (status: {dep_action.status})")
                return False
        
        return True
    
    async def _execute_analysis_action(self, plan: ExecutionPlan, action: PlannedAction) -> None:
        """Execute an analysis action using built-in LLM tools."""
        self.logger.info(f"🧠 Executing analysis action: {action.name}")
        
        # Update status to starting
        plan.update_action_status(action.id, "starting")
        await self._send_plan_update(plan)
        
        if not self.llm_tools:
            self.logger.error(f"❌ LLM tools not available for analysis action: {action.name}")
            plan.update_action_status(action.id, "failed")
            await self._send_plan_update(plan)
            return
        
        try:
            # Update status to in_progress
            plan.update_action_status(action.id, "in_progress")
            await self._send_plan_update(plan)
            
            # Determine what type of analysis this is based on action name/description
            if "format" in action.name.lower() and "pdf" in action.name.lower():
                # This is a data formatting action
                # Find the data source from dependencies
                data_source_key = None
                if action.depends_on:
                    for dep_id in action.depends_on:
                        # Look for stored result from dependency
                        data_source_key = f"tool_result_{dep_id}"
                        break
                
                if data_source_key:
                    result = await self.llm_tools.format_data_for_pdf(
                        data_source_key=data_source_key,
                        format_type="manufacturing_report",
                        title="Manufacturing Data Report"
                    )
                else:
                    result = {"error": "No data source found for formatting"}
            else:
                # Generic analysis - use a simple completion
                result = {"success": True, "analysis_result": f"Analysis completed for: {action.name}"}
            
            # Store analysis result in memory
            await self.memory.store(
                key=f"tool_result_{action.id}",
                value=result,
                tool_name="llm_analysis",
                tags=["analysis_result", "llm_tool"]
            )
            
            # Mark as completed or failed
            if isinstance(result, dict) and result.get("error"):
                plan.update_action_status(action.id, "failed")
                self.logger.error(f"❌ Analysis failed: {action.name} - {result['error']}")
            else:
                plan.update_action_status(action.id, "completed")
                self.logger.info(f"✅ Completed analysis action: {action.name}")
            
            await self._send_plan_update(plan)
            
        except Exception as e:
            self.logger.error(f"❌ Analysis action failed: {action.name} - {str(e)}")
            plan.update_action_status(action.id, "failed")
            await self._send_plan_update(plan)
    
    async def _execute_response_action(self, plan: ExecutionPlan, action: PlannedAction) -> None:
        """Execute a response action using built-in LLM tools."""
        self.logger.info(f"💬 Executing response action: {action.name}")
        
        # Update status to starting
        plan.update_action_status(action.id, "starting")
        await self._send_plan_update(plan)
        
        if not self.llm_tools:
            self.logger.error(f"❌ LLM tools not available for response action: {action.name}")
            plan.update_action_status(action.id, "failed")
            await self._send_plan_update(plan)
            return
        
        try:
            # Update status to in_progress
            plan.update_action_status(action.id, "in_progress")
            await self._send_plan_update(plan)
            
            # Collect completed actions and tool results for response generation
            completed_actions = []
            tool_results = []
            
            for plan_action in plan.actions:
                if plan_action.status == "completed":
                    completed_actions.append(plan_action.name)
                    
                    # Get tool result if it's a tool action
                    if plan_action.type.value == "tool_call":
                        result_key = f"tool_result_{plan_action.id}"
                        stored_result = await self.memory.get(result_key)
                        if stored_result:
                            tool_results.append({
                                "tool_name": plan_action.tool_name,
                                "action_name": plan_action.name,
                                "result": stored_result
                            })
            
            # Generate response using LLM tool
            result = await self.llm_tools.generate_response(
                completed_actions=completed_actions,
                user_query=plan.summary,  # Use plan summary as user query context
                tool_results=tool_results
            )
            
            # Store response result in memory
            await self.memory.store(
                key=f"tool_result_{action.id}",
                value=result,
                tool_name="llm_response",
                tags=["response_result", "llm_tool"]
            )
            
            # Mark as completed or failed
            if isinstance(result, dict) and result.get("error"):
                plan.update_action_status(action.id, "failed")
                self.logger.error(f"❌ Response generation failed: {action.name} - {result['error']}")
            else:
                plan.update_action_status(action.id, "completed")
                self.logger.info(f"✅ Completed response action: {action.name}")
            
            await self._send_plan_update(plan)
            
        except Exception as e:
            self.logger.error(f"❌ Response action failed: {action.name} - {str(e)}")
            plan.update_action_status(action.id, "failed")
            await self._send_plan_update(plan)
    
    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any], plan_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a tool using either LLM tools or MCP manager."""
        # Handle built-in LLM tools first
        if tool_name in ["search_memory", "get_memory_item"]:
            if tool_name == "search_memory":
                return await self.llm_tools.search_memory(**arguments)
            elif tool_name == "get_memory_item":
                return await self.llm_tools.get_memory_item(**arguments)
        
        # Handle MCP tools
        tool_server = await self._get_tool_server(tool_name)
        
        if tool_server == "intelycx-core":
            if tool_name == "intelycx_login":
                result = await self.mcp_manager.execute_tool(tool_name, arguments, plan_context)
                # Store JWT token if login successful
                if isinstance(result, dict) and result.get("success"):
                    self._intelycx_jwt_token = result.get("jwt_token")
                    self._intelycx_user = result.get("user")
                    self.logger.info(f"✅ Stored JWT token for user: {self._intelycx_user}")
                return result
            else:
                # Inject JWT token for other intelycx-core tools
                if not self._intelycx_jwt_token:
                    raise Exception("Manufacturing data access requires authentication")
                
                arguments_with_token = arguments.copy()
                arguments_with_token["jwt_token"] = self._intelycx_jwt_token
                result = await self.mcp_manager.execute_tool(tool_name, arguments_with_token, plan_context)
                
                # Result already stored in memory by executioner, just return it
                return result
        
        # Handle file generator tools (inject chat_id)
        elif tool_server == "intelycx-file-generator":
            # Inject chat_id for file generator tools
            if tool_name == "create_pdf" and self._chat_id:
                arguments_with_chat_id = dict(arguments)
                # Replace placeholder chat_id values or inject if missing
                current_chat_id = arguments_with_chat_id.get("chat_id")
                if (not current_chat_id or 
                    current_chat_id in ["current_chat", "current_session", "fake_data_pdf", "fake-pdf-request", "fake_pdf_request"]):
                    arguments_with_chat_id["chat_id"] = self._chat_id
                    self.logger.info(f"🔧 Injected chat_id ({self._chat_id}) for tool: {tool_name}")
                elif current_chat_id != self._chat_id:
                    # Always use the session chat_id, override planner's choice
                    arguments_with_chat_id["chat_id"] = self._chat_id
                    self.logger.info(f"🔧 Overrode chat_id '{current_chat_id}' -> '{self._chat_id}' for tool: {tool_name}")
                result = await self.mcp_manager.execute_tool(tool_name, arguments_with_chat_id, plan_context)
            else:
                result = await self.mcp_manager.execute_tool(tool_name, arguments, plan_context)
            return result
        
        # For other tools (email, etc.)
        result = await self.mcp_manager.execute_tool(tool_name, arguments, plan_context)
        return result
    
    async def _send_plan_update(self, plan: ExecutionPlan) -> None:
        """Update plan in database and send WebSocket update."""
        try:
            # Update database first (single source of truth)
            if self.plan_manager and hasattr(self.plan_manager, 'store_plan'):
                await self.plan_manager.store_plan(plan)
                self.logger.debug(f"✅ Updated plan {plan.plan_id} in database")
            
            # Update action statuses in database
            if self.plan_manager and hasattr(self.plan_manager, 'update_action_status'):
                for action in plan.actions:
                    await self.plan_manager.update_action_status(plan.plan_id, action.id, action.status)
            
            # Send WebSocket update via callback (if available)
            if self._plan_update_callback:
                await self._plan_update_callback(plan)
                
        except Exception as e:
            self.logger.warning(f"Failed to send plan update: {e}")

    async def _get_tool_server(self, tool_name: str) -> Optional[str]:
        """Get the server that provides a specific tool."""
        try:
            discovered_tools = await self.mcp_manager.list_tools()
            for tool in discovered_tools:
                if tool["name"] == tool_name:
                    return tool["server"]
        except Exception as e:
            self.logger.error(f"Error getting tool server for {tool_name}: {str(e)}")
        return None
