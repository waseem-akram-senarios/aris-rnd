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
        extracted_file_info = None
        
        if tool_results:
            results_parts = []
            for result in tool_results:
                tool_name = result.get("tool_name", "unknown")
                success = result.get("success", True)
                result_data = result.get("result", result)
                
                if tool_name == "create_pdf" and success:
                    file_url = result_data.get("file_url", "")
                    file_name = result_data.get("file_name", result_data.get("filename", "document"))
                    if file_url:
                        results_parts.append(f"Created PDF: {file_name} (Download: {file_url})")
                        extracted_file_info = {"name": file_name, "url": file_url}
                    else:
                        results_parts.append(f"Created PDF: {file_name}")
                elif tool_name == "search_memory" and success:
                    # Check if this search found files
                    files = result_data.get("files", [])
                    if files:
                        file_info = files[0]  # Get the first file
                        file_name = file_info.get("name", "document")
                        file_url = file_info.get("url", "")
                        if file_url:
                            results_parts.append(f"Found file: {file_name} (Download: {file_url})")
                            extracted_file_info = {"name": file_name, "url": file_url}
                        else:
                            results_parts.append(f"Found file: {file_name}")
                    else:
                        # Check if we found items with file URLs
                        items = result_data.get("items", [])
                        for item in items:
                            if isinstance(item.get("value"), dict):
                                file_url = item["value"].get("file_url")
                                file_name = (
                                    item["value"].get("file_name") or 
                                    item["value"].get("filename") or 
                                    item["value"].get("name") or 
                                    "document"
                                )
                                if file_url:
                                    results_parts.append(f"Found file: {file_name} (Download: {file_url})")
                                    extracted_file_info = {"name": file_name, "url": file_url}
                                    break
                        else:
                            results_parts.append("Searched memory for files")
                elif tool_name == "get_fake_data" and success:
                    results_parts.append("Retrieved manufacturing data successfully")
                elif tool_name == "intelycx_login" and success:
                    results_parts.append("Authentication completed")
            
            if results_parts:
                results_summary = f"Results:\n" + "\n".join([f"- {result}" for result in results_parts])
        
        # Create response generation prompt with file information
        file_info_text = ""
        if extracted_file_info:
            file_info_text = f"\nFILE INFORMATION:\nFile Name: {extracted_file_info['name']}\nDownload URL: {extracted_file_info['url']}"
        
        response_prompt = f"""Generate a professional response to the user based on the completed actions and results.

USER QUERY: "{user_query}"

{actions_summary}

{results_summary}

{file_info_text}

Generate a clear, helpful response that:
1. Acknowledges what was accomplished
2. Provides the actual download URL if available
3. Shows the exact URL in the response text
4. Confirms successful completion
5. Is professional and user-friendly

IMPORTANT: If there is a download URL, include it in the response text so the user can see and use it.

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
    
    async def search_memory(self, **kwargs) -> Dict[str, Any]:
        """
        Search session memory for previous tool results and data.
        
        Args:
            search_type: Type of search ("files", "tool_results", "all")
            tool_name: Filter by specific tool name (optional)
            tags: Filter by tags (optional)
            
        Returns:
            Dict containing found memory items
        """
        search_type = kwargs.get("search_type", "all")
        tool_name = kwargs.get("tool_name")
        tags = kwargs.get("tags", [])
        
        self.logger.info(f"🔍 Searching memory: type={search_type}, tool={tool_name}, tags={tags}")
        
        try:
            # Get memory keys based on search criteria
            if tool_name:
                # Search by tool name first
                matching_keys = await self.memory.search_by_tool(tool_name)
            elif tags:
                # Search by tags
                matching_keys = []
                for tag in tags:
                    tag_keys = await self.memory.search_by_tag(tag)
                    matching_keys.extend(tag_keys)
                matching_keys = list(set(matching_keys))  # Remove duplicates
            else:
                # Get all keys
                matching_keys = await self.memory.list_keys()
            
            found_items = []
            
            for key in matching_keys:
                # Apply additional filters
                include_item = True
                
                # Filter by search type
                if search_type == "files":
                    # Look for file-related results
                    if not ("create_pdf" in key or "file" in key.lower() or key.startswith("tool_result_")):
                        include_item = False
                elif search_type == "tool_results":
                    # Look for tool results
                    if not key.startswith("tool_result_"):
                        include_item = False
                
                if include_item:
                    # Get the actual value and metadata
                    value = await self.memory.get(key)
                    if value is not None:
                        # Get metadata if available
                        try:
                            metadata = await self.memory.get_metadata(key)
                            found_items.append({
                                "key": key,
                                "tool_name": metadata.tool_name if metadata else "unknown",
                                "tags": metadata.tags if metadata else [],
                                "created_at": metadata.created_at.isoformat() if metadata else "unknown",
                                "size": metadata.size_bytes if metadata else len(str(value)),
                                "value": value
                            })
                        except:
                            # Fallback if metadata not available
                            found_items.append({
                                "key": key,
                                "tool_name": "unknown",
                                "tags": [],
                                "created_at": "unknown",
                                "size": len(str(value)),
                                "value": value
                            })
            
            self.logger.info(f"✅ Found {len(found_items)} memory items matching criteria")
            
            # Extract file URLs for easy access
            file_urls = []
            for item in found_items:
                if isinstance(item["value"], dict):
                    file_url = item["value"].get("file_url")
                    # Try multiple filename fields (same as in structured response data)
                    file_name = (
                        item["value"].get("file_name") or 
                        item["value"].get("filename") or 
                        item["value"].get("name") or 
                        "document"
                    )
                    if file_url:
                        file_urls.append({
                            "name": file_name,
                            "url": file_url,
                            "tool": item["tool_name"],
                            "created_at": item["created_at"],
                            "key": item["key"]
                        })
            
            # Create a detailed summary for the analysis tool
            summary_parts = []
            if file_urls:
                summary_parts.append(f"Found {len(file_urls)} files:")
                for file_info in file_urls:
                    summary_parts.append(f"- {file_info['name']}: {file_info['url']}")
            
            if len(found_items) > len(file_urls):
                other_items = len(found_items) - len(file_urls)
                summary_parts.append(f"Plus {other_items} other memory items")
            
            detailed_summary = "\n".join(summary_parts) if summary_parts else "No matching items found"
            
            return {
                "success": True,
                "search_type": search_type,
                "total_found": len(found_items),
                "items": found_items,
                "files": file_urls,
                "summary": f"Found {len(found_items)} items ({len(file_urls)} files)",
                "detailed_summary": detailed_summary,
                "file_count": len(file_urls)
            }
            
        except Exception as e:
            self.logger.error(f"❌ Memory search failed: {str(e)}")
            return {"error": f"Memory search failed: {str(e)}"}
    
    async def get_memory_item(self, **kwargs) -> Dict[str, Any]:
        """
        Get a specific memory item by key.
        
        Args:
            key: Memory key to retrieve
            
        Returns:
            Dict containing the memory item value
        """
        key = kwargs.get("key")
        if not key:
            return {"error": "key parameter is required"}
        
        self.logger.info(f"🔍 Getting memory item: {key}")
        
        try:
            value = await self.memory.get(key)
            if value is not None:
                self.logger.info(f"✅ Found memory item: {key}")
                return {
                    "success": True,
                    "key": key,
                    "value": value,
                    "found": True
                }
            else:
                self.logger.warning(f"⚠️ Memory item not found: {key}")
                return {
                    "success": True,
                    "key": key,
                    "found": False,
                    "message": f"No item found with key: {key}"
                }
                
        except Exception as e:
            self.logger.error(f"❌ Memory retrieval failed: {str(e)}")
            return {"error": f"Memory retrieval failed: {str(e)}"}
