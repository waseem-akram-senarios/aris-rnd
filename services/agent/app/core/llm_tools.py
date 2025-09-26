"""
Built-in LLM tools for the agent executioner.

These tools allow the executioner to call the LLM for specific tasks like
data formatting and response generation as part of plan execution.
"""

import logging
from typing import Dict, Any, Optional
from ..llm.bedrock import BedrockClient


class LLMTools:
    """Built-in LLM tools for agent execution."""
    
    def __init__(self, bedrock_client: BedrockClient, memory_manager, logger: Optional[logging.Logger] = None):
        self.bedrock = bedrock_client
        self.memory = memory_manager
        self.logger = logger or logging.getLogger(__name__)
    
    async def format_data_for_pdf(self, **kwargs) -> Dict[str, Any]:
        """
        Format raw data into a structured format suitable for PDF creation.
        
        Args:
            data_source_key: Memory key containing the raw data to format
            format_type: Type of formatting (e.g., "manufacturing_report")
            title: Title for the formatted content
            
        Returns:
            Dict containing formatted content and metadata
        """
        data_source_key = kwargs.get("data_source_key")
        format_type = kwargs.get("format_type", "manufacturing_report")
        title = kwargs.get("title", "Data Report")
        
        if not data_source_key:
            return {"error": "data_source_key parameter is required"}
        
        # Retrieve raw data from memory
        raw_data = await self.memory.get(data_source_key)
        if not raw_data:
            return {"error": f"No data found for key: {data_source_key}"}
        
        self.logger.info(f"🧠 Formatting data from {data_source_key} for PDF ({format_type})")
        
        # Create formatting prompt
        formatting_prompt = f"""Format the following raw data into a well-structured document suitable for PDF creation.

TITLE: {title}
FORMAT TYPE: {format_type}

RAW DATA:
{raw_data}

Please format this data into a clear, professional document structure with:
1. Executive Summary
2. Key Metrics and Highlights  
3. Detailed Sections (organized by data type)
4. Conclusions and Insights

Return ONLY the formatted content that should go into the PDF document."""

        try:
            # Use LLM to format the data
            formatted_content = await self.bedrock.converse(
                model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
                messages=[{"role": "user", "content": [{"text": formatting_prompt}]}],
                temperature=0.1,
                system=[{"text": "You are a data formatting specialist. Format raw data into professional, well-structured documents."}]
            )
            
            self.logger.info(f"✅ Successfully formatted data: {len(formatted_content)} chars")
            
            return {
                "success": True,
                "formatted_content": formatted_content,
                "title": title,
                "format_type": format_type,
                "original_data_size": len(str(raw_data)),
                "formatted_size": len(formatted_content)
            }
            
        except Exception as e:
            self.logger.error(f"❌ Data formatting failed: {str(e)}")
            return {"error": f"Data formatting failed: {str(e)}"}
    
    async def generate_response(self, **kwargs) -> Dict[str, Any]:
        """
        Generate a final response message based on completed actions and results.
        
        Args:
            completed_actions: List of completed action summaries
            user_query: Original user request
            tool_results: List of tool execution results
            
        Returns:
            Dict containing the generated response message
        """
        completed_actions = kwargs.get("completed_actions", [])
        user_query = kwargs.get("user_query", "")
        tool_results = kwargs.get("tool_results", [])
        
        self.logger.info(f"🧠 Generating response for user query with {len(completed_actions)} completed actions")
        
        # Build context about what was accomplished
        actions_summary = ""
        if completed_actions:
            actions_summary = f"Completed actions:\n" + "\n".join([f"- {action}" for action in completed_actions])
        
        # Build tool results summary
        results_summary = ""
        if tool_results:
            results_parts = []
            for result in tool_results:
                tool_name = result.get("tool_name", "unknown")
                success = result.get("success", True)
                if tool_name == "create_pdf" and success:
                    file_url = result.get("file_url", "")
                    file_name = result.get("file_name", "document")
                    results_parts.append(f"Created PDF: {file_name} ({file_url})")
                elif tool_name == "get_fake_data" and success:
                    results_parts.append("Retrieved manufacturing data successfully")
                elif tool_name == "intelycx_login" and success:
                    results_parts.append("Authentication completed")
            
            if results_parts:
                results_summary = f"Results:\n" + "\n".join([f"- {result}" for result in results_parts])
        
        # Create response generation prompt
        response_prompt = f"""Generate a professional response to the user based on the completed actions and results.

USER QUERY: "{user_query}"

{actions_summary}

{results_summary}

Generate a clear, helpful response that:
1. Acknowledges what was accomplished
2. Provides relevant details (like download links)
3. Confirms successful completion
4. Is professional and user-friendly

Return ONLY the response message text."""

        try:
            # Use LLM to generate the response
            response_text = await self.bedrock.converse(
                model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
                messages=[{"role": "user", "content": [{"text": response_prompt}]}],
                temperature=0.2,
                system=[{"text": "You are ARIS, a helpful manufacturing assistant. Generate professional responses acknowledging completed actions."}]
            )
            
            self.logger.info(f"✅ Successfully generated response: {len(response_text)} chars")
            
            return {
                "success": True,
                "response_text": response_text,
                "actions_count": len(completed_actions),
                "results_count": len(tool_results)
            }
            
        except Exception as e:
            self.logger.error(f"❌ Response generation failed: {str(e)}")
            return {"error": f"Response generation failed: {str(e)}"}
