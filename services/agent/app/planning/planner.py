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
        conversation_context: Optional[List[Dict[str, Any]]] = None,
        chat_id: Optional[str] = None
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
        planning_prompt = self._create_planning_prompt(user_query, available_tools, conversation_context, chat_id)
        
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
        conversation_context: Optional[List[Dict[str, Any]]] = None,
        chat_id: Optional[str] = None
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
        
        # Add chat ID context for file generation tools
        chat_context = ""
        if chat_id:
            chat_context = f"\nCURRENT CHAT SESSION ID: {chat_id}\n(Use this exact chat_id for any file generation tools like create_pdf)\n"
        
        prompt = f"""Analyze this user query and create a detailed execution plan using the available tools.

USER QUERY: "{user_query}"{chat_context}

{context_section}AVAILABLE TOOLS:
{chr(10).join(tool_descriptions)}

Create a JSON execution plan with this structure:"""
        
        prompt += """
{
    "summary": "Brief description of what will be accomplished",
    "actions": [
        {
            "id": "unique-uuid-string",
            "type": "tool_call|analysis|response",
            "name": "Human-readable action name",
            "description": "What this action will accomplish",
            "tool_name": "exact_tool_name_if_tool_call",
            "arguments": {"param1": "value1", "attachment_urls": ["{{previous_action_id.file_url}}"]},
            "depends_on": ["previous_action_uuid"]
        }
    ]
}"""
        
        prompt += """

PLANNING GUIDELINES:
1. Generate unique UUID-style strings for each action ID (e.g., "a1b2c3d4-e5f6-7890-abcd-ef1234567890")
2. Only use tools that are actually available in the list above
3. For manufacturing queries, typically use get_machine, get_machine_group, or get_production_summary
4. For email requests, use send_email
5. For fake data requests, use get_fake_data with data_type: "all" (valid options: "all", "production", "inventory", "alerts", "metrics", "energy")
6. For file generation, always use the provided chat_id (never use placeholders like "fake-pdf-request")
7. DATA FORMATTING: When creating PDFs with data from tools like get_fake_data, ALWAYS include an analysis action to format the raw data into readable content BEFORE creating the PDF:
   - Get data → Analysis action (format data) → Create PDF with formatted content
   - Never put raw JSON directly into PDF content
8. ACTION TYPE SELECTION - CRITICAL:
   - Use "tool_call" type when a FUNCTION/TOOL exists (e.g., list_mcp_tools, get_fake_data, send_email, create_pdf)
   - Use "analysis" type ONLY for reasoning/formatting/summarizing data that doesn't have a specific tool
   - NEVER use "analysis" when a tool function exists - ALWAYS prefer "tool_call" with the actual tool_name
   - Example: "List available tools" → tool_call with tool_name="list_mcp_tools", NOT analysis
   - Example: "Format this data for a report" → analysis (no specific tool for formatting)
9. End with a response action to synthesize results
10. Consider dependencies between actions - use the actual UUID of dependent actions
11. Be specific with tool arguments based on the user query
12. If the query is unclear, plan to ask for clarification
13. Do not include time estimates or duration fields
14. TEMPLATE VARIABLES: When referencing results from previous actions, use DOUBLE-BRACE template syntax:
    - For file URLs: "{{action_id.file_url}}" where action_id is the ACTUAL UUID you generated for that action
    - For analysis results: "{{action_id.result}}" 
    - For any field: "{{action_id.field_name}}"
    - CRITICAL: Always use DOUBLE braces {{ }} not single braces { }
    - CRITICAL: "a1b2c3d4-e5f6-7890-abcd-ef1234567890" is just an EXAMPLE - you MUST use the actual UUID you created for the action
15. EMAIL ATTACHMENTS: Always use template variables for attachment URLs, never hardcode filenames
    - Example: If you created a PDF action with id "f4e2a1b3-8c9d-4e5f-a6b7-c8d9e0f1a2b3", then use "{{f4e2a1b3-8c9d-4e5f-a6b7-c8d9e0f1a2b3.file_url}}"
    - WRONG: Using example IDs like "{{a1b2c3d4-e5f6-7890-abcd-ef1234567890.file_url}}"
    - RIGHT: Using the actual action ID you generated in your plan
16. MEMORY ACCESS PATTERNS - CRITICAL:
    - When user says "put THAT content in a PDF", prefer direct tool call over search_memory
    - If the previous action was list_mcp_tools, reference it directly: "{{list_tools_action_id.result}}"
    - Only use search_memory when you need to find something from earlier in the conversation (not the immediately previous action)
    - search_memory returns a wrapper object - template resolution will extract the relevant content automatically
    - Example GOOD: list_mcp_tools → create_pdf with "{{list_action_id.result}}"
    - Example BAD: list_mcp_tools → search_memory → create_pdf (unnecessary search step)
17. CROSS-PLAN REFERENCES - CRITICAL FOR EMAIL/FILE OPERATIONS:
    - When user asks to email/use a file from a PREVIOUS conversation turn, you MUST use search_memory to find it
    - Then use the search_memory action's result in your template: "{{search_action_id.result}}"
    - The template resolver will automatically extract file URLs from search results
    - Example: User says "send that PDF" → search_memory for PDF → send_email with "{{search_id.result}}"
    - NEVER use example UUIDs from guidelines - they don't exist in memory!

CRITICAL: CONSERVATIVE PLANNING REQUIRED
18. ONLY create PDFs when explicitly requested (e.g., "create a PDF", "put this in a file", "generate a document")
19. For simple questions like "What is X?" or "Tell me about Y" or "Explain Z", use EXACTLY 2 actions:
    - ONE analysis action to understand the query
    - ONE response action to provide the answer
20. Do NOT create multiple analysis actions for the same topic
21. Do NOT assume the user wants documentation unless they specifically ask for it
22. Do NOT create comprehensive multi-step plans for simple explanation requests
23. MAXIMUM 2 actions for explanation/information requests
24. When in doubt, choose the SIMPLEST approach (1 analysis + 1 response)

Return ONLY the JSON plan, no other text."""
        
        return prompt

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
