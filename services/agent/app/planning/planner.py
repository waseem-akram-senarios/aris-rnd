"""Agent planning service for analyzing user queries and creating execution plans."""

import uuid
import json
import logging
from typing import List, Dict, Any, Optional, Tuple

from .models import ExecutionPlan, PlannedAction, ActionType
from ..llm.bedrock import BedrockClient


class AgentPlanner:
    """Service for creating execution plans based on user queries and available tools."""
    
    def __init__(self, bedrock_client: BedrockClient, logger: Optional[logging.Logger] = None):
        self.bedrock = bedrock_client
        self.logger = logger or logging.getLogger(__name__)
        
    async def create_execution_plan(
        self, 
        user_query: str, 
        available_tools: List[Dict[str, Any]],
        conversation_context: Optional[List[Dict[str, Any]]] = None
    ) -> ExecutionPlan:
        """
        Analyze user query and create an execution plan.
        
        Args:
            user_query: The user's request
            available_tools: List of available tools in Bedrock format
            conversation_context: Recent conversation history for context
            
        Returns:
            ExecutionPlan with planned actions
        """
        plan_id = str(uuid.uuid4())
        
        # Create planning prompt
        planning_prompt = self._create_planning_prompt(user_query, available_tools, conversation_context)
        
        # Use LLM to analyze query and create plan
        self.logger.info("🧠 Creating execution plan for user query...")
        
        try:
            # Use a simple message for planning (no tool calling in planning phase)
            planning_messages = [{"role": "user", "content": [{"text": planning_prompt}]}]
            
            plan_response = await self.bedrock.converse(
                model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
                messages=planning_messages,
                temperature=0.1,
                system=[{"text": "You are an expert AI agent planner. Analyze user queries and create detailed execution plans using available tools."}]
            )
            
            # Parse the plan from the response
            execution_plan = self._parse_plan_response(plan_id, user_query, plan_response, available_tools)
            
            self.logger.info(f"📋 Created execution plan with {len(execution_plan.actions)} actions")
            return execution_plan
            
        except Exception as e:
            self.logger.error(f"❌ Error creating execution plan: {str(e)}")
            # Fallback: create a simple plan
            return self._create_fallback_plan(plan_id, user_query, available_tools)
    
    def _create_planning_prompt(
        self, 
        user_query: str, 
        available_tools: List[Dict[str, Any]],
        conversation_context: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Create a prompt for the planning LLM call."""
        
        # Extract tool information
        tool_descriptions = []
        for tool in available_tools:
            tool_spec = tool.get("toolSpec", {})
            name = tool_spec.get("name", "unknown")
            description = tool_spec.get("description", "No description")
            
            # Get input schema details
            input_schema = tool_spec.get("inputSchema", {}).get("json", {})
            properties = input_schema.get("properties", {})
            required = input_schema.get("required", [])
            
            param_info = []
            for param_name, param_details in properties.items():
                param_type = param_details.get("type", "unknown")
                param_desc = param_details.get("description", "No description")
                is_required = param_name in required
                param_info.append(f"  - {param_name} ({param_type}{'*' if is_required else ''}): {param_desc}")
            
            tool_descriptions.append(f"• {name}: {description}\n" + "\n".join(param_info))
        
        context_section = ""
        if conversation_context:
            context_section = f"""
CONVERSATION CONTEXT:
{json.dumps(conversation_context[-3:], indent=2)}  # Last 3 messages for context

"""
        
        return f"""Analyze this user query and create a detailed execution plan using the available tools.

USER QUERY: "{user_query}"

{context_section}AVAILABLE TOOLS:
{chr(10).join(tool_descriptions)}

Create a JSON execution plan with this structure:
{{
    "summary": "Brief description of what will be accomplished",
    "actions": [
        {{
            "id": "unique-uuid-string",
            "type": "tool_call|analysis|response",
            "name": "Human-readable action name",
            "description": "What this action will accomplish",
            "tool_name": "exact_tool_name_if_tool_call",
            "arguments": {{"param1": "value1"}} // if tool_call,
            "depends_on": ["previous_action_uuid"] // if depends on other actions
        }}
    ]
}}

PLANNING GUIDELINES:
1. Generate unique UUID-style strings for each action ID (e.g., "a1b2c3d4-e5f6-7890-abcd-ef1234567890")
2. Only use tools that are actually available in the list above
3. For manufacturing queries, typically use get_machine, get_machine_group, or get_production_summary
4. For email requests, use send_email
5. Include analysis actions for complex reasoning
6. End with a response action to synthesize results
7. Consider dependencies between actions - use the actual UUID of dependent actions
8. Be specific with tool arguments based on the user query
9. If the query is unclear, plan to ask for clarification
10. Do not include time estimates or duration fields

Return ONLY the JSON plan, no other text."""

    def _parse_plan_response(
        self, 
        plan_id: str, 
        user_query: str, 
        plan_response: str, 
        available_tools: List[Dict[str, Any]]
    ) -> ExecutionPlan:
        """Parse the LLM response into an ExecutionPlan."""
        
        try:
            # Extract JSON from response
            plan_json = json.loads(plan_response.strip())
            
            # Create planned actions with UUID generation
            actions = []
            action_id_mapping = {}  # Map old IDs to new UUIDs for dependency resolution
            
            # First pass: generate UUIDs for all actions
            action_data_list = plan_json.get("actions", [])
            for action_data in action_data_list:
                old_id = action_data.get("id", f"action_{len(action_id_mapping)}")
                new_uuid = str(uuid.uuid4())
                action_id_mapping[old_id] = new_uuid
            
            # Second pass: create actions with proper dependency mapping
            for action_data in action_data_list:
                old_id = action_data.get("id", f"action_{len(actions)}")
                new_uuid = action_id_mapping[old_id]
                
                # Handle dependencies - map old IDs to new UUIDs
                depends_on = action_data.get("depends_on")
                if depends_on:
                    new_depends_on = []
                    for dep_id in depends_on:
                        if dep_id in action_id_mapping:
                            new_depends_on.append(action_id_mapping[dep_id])
                        else:
                            self.logger.warning(f"⚠️ Dependency '{dep_id}' not found in action mapping")
                    depends_on = new_depends_on if new_depends_on else None
                
                action = PlannedAction(
                    id=new_uuid,
                    type=ActionType(action_data.get("type", "analysis")),
                    name=action_data.get("name", "Unknown action"),
                    description=action_data.get("description", "No description"),
                    tool_name=action_data.get("tool_name"),
                    arguments=action_data.get("arguments"),
                    depends_on=depends_on
                )
                actions.append(action)
            
            return ExecutionPlan(
                plan_id=plan_id,
                user_query=user_query,
                summary=plan_json.get("summary", "Execute user request"),
                actions=actions
            )
            
        except Exception as e:
            self.logger.warning(f"⚠️ Failed to parse plan response: {str(e)}")
            return self._create_fallback_plan(plan_id, user_query, available_tools)
    
    def _create_fallback_plan(
        self, 
        plan_id: str, 
        user_query: str, 
        available_tools: List[Dict[str, Any]]
    ) -> ExecutionPlan:
        """Create a simple fallback plan when planning fails."""
        
        analyze_id = str(uuid.uuid4())
        respond_id = str(uuid.uuid4())
        
        actions = [
            PlannedAction(
                id=analyze_id,
                type=ActionType.ANALYSIS,
                name="Analyze user request",
                description="Understand what the user is asking for"
            ),
            PlannedAction(
                id=respond_id,
                type=ActionType.RESPONSE,
                name="Provide response",
                description="Generate a helpful response to the user",
                depends_on=[analyze_id]
            )
        ]
        
        return ExecutionPlan(
            plan_id=plan_id,
            user_query=user_query,
            summary="Process user request and provide response",
            actions=actions
        )
