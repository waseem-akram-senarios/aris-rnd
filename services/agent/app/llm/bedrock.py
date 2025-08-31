from typing import Dict, Any, Optional, List
import logging
import json

import boto3


class BedrockClient:
    def __init__(self, region: str):
        config = boto3.session.Config(connect_timeout=5, read_timeout=60, retries={"max_attempts": 2})
        self._client = boto3.client("bedrock-runtime", region_name=region, config=config)
        self._logger = logging.getLogger("llm.bedrock")

    async def converse(
        self, 
        model_id: str, 
        messages: List[Dict[str, Any]], 
        system: Optional[List] = None, 
        temperature: float = 0.0,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_executor: Optional[Any] = None,
        max_recursions: int = 5
    ) -> str:
        """Converse with optional tool support using Bedrock's capabilities."""
        
        # If no tools provided, use simple flow
        if not tools or not tool_executor:
            self._logger.info(f"Bedrock.converse model_id={model_id} temp={temperature} msgs={len(messages)} (simple mode)")
            
            resp = self._client.converse(
                modelId=model_id,
                messages=messages,
                system=system or [],
                inferenceConfig={"temperature": temperature},
            )
            self._logger.debug(f"Bedrock raw response keys: {list(resp.keys())}")
            message = resp["output"]["message"]
            return "\n".join([c.get("text", "") for c in message.get("content", [])])
        
        # Tool-enabled flow
        self._logger.info(f"Bedrock.converse model_id={model_id} temp={temperature} msgs={len(messages)} (tools mode) - {len(tools)} tools available")
        self._logger.info(f"Available tools: {[tool['toolSpec']['name'] for tool in tools]}")
        
        recursion_count = 0
        current_messages = messages.copy()
        
        while recursion_count < max_recursions:
            # Prepare API call parameters
            api_params = {
                "modelId": model_id,
                "messages": current_messages,
                "inferenceConfig": {"temperature": temperature}
            }
            
            # Add system message if provided
            if system:
                api_params["system"] = system
            
            # Add tools configuration
            api_params["toolConfig"] = {"tools": tools}
            
            # Make API call
            response = self._client.converse(**api_params)
            
            message = response["output"]["message"]
            current_messages.append({"role": "assistant", "content": message["content"]})
            
            # Check if the model wants to use tools
            stop_reason = response.get("stopReason")
            if stop_reason == "tool_use":
                # Execute tool calls
                tool_results = []
                for content_item in message["content"]:
                    if content_item.get("toolUse"):
                        tool_use = content_item["toolUse"]
                        tool_name = tool_use["name"]
                        tool_input = tool_use["input"]
                        tool_id = tool_use["toolUseId"]
                        
                        self._logger.debug(f"🔧 TOOL CALL: {tool_name}")
                        self._logger.debug(f"📥 TOOL INPUT: {json.dumps(tool_input, indent=2)}")
                        
                        try:
                            # Execute the tool
                            result = await tool_executor.execute_tool(tool_name, tool_input)
                            
                            self._logger.debug(f"✅ TOOL SUCCESS: {tool_name}")
                            # Don't log full tool output here - it's already logged by MCPServerManager
                            result_size = len(json.dumps(result, default=str))
                            self._logger.debug(f"📤 TOOL OUTPUT: {result_size} characters")
                            
                            tool_results.append({
                                "toolResult": {
                                    "toolUseId": tool_id,
                                    "content": [{"text": json.dumps(result)}]
                                }
                            })
                        except Exception as e:
                            self._logger.error(f"❌ TOOL ERROR: {tool_name} - {str(e)}")
                            tool_results.append({
                                "toolResult": {
                                    "toolUseId": tool_id,
                                    "content": [{"text": f"Error: {str(e)}"}],
                                    "status": "error"
                                }
                            })
                
                # Add tool results to messages
                current_messages.append({"role": "user", "content": tool_results})
                recursion_count += 1
            else:
                # No more tool calls, return the final response
                text_content = []
                for content_item in message.get("content", []):
                    if "text" in content_item:
                        text_content.append(content_item["text"])
                
                return "\n".join(text_content)
        
        # Max recursions reached
        self._logger.warning(f"Max tool recursions ({max_recursions}) reached")
        return "I apologize, but I've reached the maximum number of tool calls allowed."


