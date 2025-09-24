"""Agent executioner for executing planned actions."""

import logging
from typing import Dict, Any, Optional, Callable, Awaitable, TYPE_CHECKING

from .models import ExecutionPlan, PlannedAction, ChainOfThoughtMessage, create_plan_update_websocket_message
from ..mcp import MCPServerManager
from ..core.memory import SessionMemoryManager

if TYPE_CHECKING:
    from .observer import PlanManager


class AgentExecutioner:
    """Executes planned actions and updates plan status."""
    
    def __init__(
        self, 
        mcp_manager: MCPServerManager, 
        memory: SessionMemoryManager,
        plan_manager: Optional['PlanManager'] = None,
        logger: Optional[logging.Logger] = None
    ):
        self.mcp_manager = mcp_manager
        self.memory = memory
        self.plan_manager = plan_manager
        self.logger = logger or logging.getLogger(__name__)
        
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
            # Mark plan as in progress
            plan.update_plan_status("in_progress")
            await self._send_plan_update(plan)
            
            # Execute only tool_call actions - analysis and response will be handled by LLM later
            for action in plan.actions:
                if action.type.value == "tool_call" and action.tool_name:
                    await self._execute_tool_action(plan, action)
                    
                    # Auto-update plan status based on action results
                    plan.auto_update_plan_status()
                    await self._send_plan_update(plan)
                    
                    # Stop execution if plan failed
                    if plan.status == "error":
                        self.logger.error(f"❌ Plan execution failed: {plan.plan_id}")
                        return plan
                elif action.type.value == "analysis":
                    # Mark analysis actions as starting - LLM will handle the actual analysis
                    plan.update_action_status(action.id, "starting")
                    await self._send_plan_update(plan)
                    self.logger.info(f"🧠 Analysis action '{action.name}' marked as starting - will be completed by LLM")
                elif action.type.value == "response":
                    # Mark response actions as starting - LLM will handle the actual response
                    plan.update_action_status(action.id, "starting") 
                    await self._send_plan_update(plan)
                    self.logger.info(f"💬 Response action '{action.name}' marked as starting - will be completed by LLM")
            
            # Final status update
            final_status = plan.auto_update_plan_status()
            self.logger.info(f"✅ Completed execution of plan {plan.plan_id} with status: {final_status}")
            
        except Exception as e:
            # Mark plan as error if execution fails
            plan.update_plan_status("error")
            await self._send_plan_update(plan)
            self.logger.error(f"❌ Plan execution error: {plan.plan_id} - {str(e)}")
            raise
        
        return plan
    
    async def _execute_tool_action(self, plan: ExecutionPlan, action: PlannedAction) -> None:
        """Execute a tool call action."""
        self.logger.info(f"🔧 Executing tool action: {action.tool_name}")
        
        # Create plan context for MCP manager
        plan_context = {
            "plan": plan,
            "action_id": action.id,
            "plan_manager": self.plan_manager,
            "logger": self.logger
        }
        
        try:
            # Execute the tool with plan context (MCP manager will handle all status updates)
            result = await self._execute_tool(action.tool_name, action.arguments or {}, plan_context)
            
            self.logger.info(f"✅ Completed tool action: {action.tool_name}")
            
        except Exception as e:
            self.logger.error(f"❌ Tool action failed: {action.tool_name} - {str(e)}")
            raise
    
    async def _execute_analysis_action(self, plan: ExecutionPlan, action: PlannedAction) -> None:
        """Execute an analysis action."""
        self.logger.info(f"🧠 Executing analysis action: {action.name}")
        
        # Update status to starting
        plan.update_action_status(action.id, "starting")
        await self._send_plan_update(plan)
        
        # Simulate analysis (in real implementation, this might call LLM)
        plan.update_action_status(action.id, "in_progress")
        await self._send_plan_update(plan)
        
        # Mark as completed
        plan.update_action_status(action.id, "completed")
        await self._send_plan_update(plan)
        
        self.logger.info(f"✅ Completed analysis action: {action.name}")
    
    async def _execute_response_action(self, plan: ExecutionPlan, action: PlannedAction) -> None:
        """Execute a response action."""
        self.logger.info(f"💬 Executing response action: {action.name}")
        
        # Update status to starting
        plan.update_action_status(action.id, "starting")
        await self._send_plan_update(plan)
        
        # Simulate response generation
        plan.update_action_status(action.id, "in_progress")
        await self._send_plan_update(plan)
        
        # Mark as completed
        plan.update_action_status(action.id, "completed")
        await self._send_plan_update(plan)
        
        self.logger.info(f"✅ Completed response action: {action.name}")
    
    async def _execute_tool(self, tool_name: str, arguments: Dict[str, Any], plan_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a tool using the MCP manager."""
        # Handle authentication for intelycx-core tools
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
                
                # Let memory manager handle the result
                return await self.memory.handle_tool_result(tool_name, arguments, result)
        
        # Handle file generator tools (inject chat_id)
        elif tool_server == "intelycx-file-generator":
            # Inject chat_id for file generator tools
            if tool_name == "create_pdf" and self._chat_id:
                arguments_with_chat_id = dict(arguments)
                # Replace placeholder chat_id values or inject if missing
                current_chat_id = arguments_with_chat_id.get("chat_id")
                if (not current_chat_id or 
                    current_chat_id in ["current_chat", "current_session", "fake_data_pdf"]):
                    arguments_with_chat_id["chat_id"] = self._chat_id
                    self.logger.info(f"🔧 Injected chat_id ({self._chat_id}) for tool: {tool_name}")
                result = await self.mcp_manager.execute_tool(tool_name, arguments_with_chat_id, plan_context)
            else:
                result = await self.mcp_manager.execute_tool(tool_name, arguments, plan_context)
            return await self.memory.handle_tool_result(tool_name, arguments, result)
        
        # For other tools (email, etc.)
        result = await self.mcp_manager.execute_tool(tool_name, arguments, plan_context)
        return await self.memory.handle_tool_result(tool_name, arguments, result)
    
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
