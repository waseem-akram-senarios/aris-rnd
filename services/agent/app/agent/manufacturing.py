from .base import BaseAgent, AgentResponse
from typing import Any, Dict, Optional, List
from pathlib import Path
from ..utils.documents import get_document_content_from_s3
from ..utils.file_handlers import FileProcessor
from ..llm.bedrock import BedrockClient

from ..mcp import MCPServerManager
from ..config.settings import load_settings
import logging


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
            self._logger.info("🚀 Starting MCP servers...")
            start_results = await self._mcp_manager.start_all_servers()
            self._logger.info(f"📊 MCP START RESULTS: {start_results}")
            self._mcp_initialized = True
        
        # Get available tools from MCP servers
        tools = []
        self._logger.info(f"🔍 MCP SERVERS: Found {len(self._mcp_manager.servers)} configured servers")
        self._logger.info(f"🔗 MCP CONNECTIONS: {len(self._mcp_manager.connections)} active connections")
        
        for server_name, server_config in self._mcp_manager.servers.items():
            self._logger.info(f"📋 Checking server: {server_name}")
            if server_name in self._mcp_manager.connections:
                self._logger.info(f"✅ Server {server_name} is connected")
                # Get tools based on server type
                if server_name == "intelycx-core":
                    intelycx_tools = self._get_intelycx_core_tools()
                    tools.extend(intelycx_tools)
                    self._logger.info(f"🛠️  Added {len(intelycx_tools)} tools from {server_name}")
                elif server_name == "intelycx-email":
                    email_tools = self._get_intelycx_email_tools()
                    tools.extend(email_tools)
                    self._logger.info(f"📧 Added {len(email_tools)} tools from {server_name}")
            else:
                self._logger.warning(f"⚠️  Server {server_name} is not connected")
        
        self._logger.info(f"🎯 TOTAL TOOLS AVAILABLE: {len(tools)}")
        
        # Create system prompt based on tool availability
        if tools:
            system_prompt = "You are ARIS, a helpful manufacturing assistant with access to production data tools and email capabilities. You can query machine information, machine group details, production summaries, and send email notifications. ALWAYS use the available tools when users ask about machines, production lines, manufacturing metrics, or need to send emails/notifications. Never make up or guess information - only provide data from actual tool calls. Maintain context across the conversation and remember user-provided details such as their name during this session. When documents are provided, analyze them and answer questions based on their content."
        else:
            system_prompt = "You are ARIS, a helpful manufacturing assistant. Currently, I don't have access to production data tools or email capabilities, so I cannot provide specific information about machines, machine groups, production metrics, or send notifications. Please let the user know that the tools are temporarily unavailable and suggest they try again later. Never make up or fabricate manufacturing data. Be honest about your limitations."
        
        # Use the enhanced converse method with tools
        text = await self._bedrock.converse(
            model_id=model_id,
            messages=self._messages[-20:],
            tools=tools,
            tool_executor=self._mcp_manager,
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
    
    def _get_intelycx_core_tools(self) -> List[Dict[str, Any]]:
        """Get tool definitions for Intelycx Core API."""
        return [
            {
                "toolSpec": {
                    "name": "get_machine",
                    "description": "Get detailed information about a specific machine including status, location, maintenance schedule, and performance metrics.",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "machine_id": {
                                    "type": "string",
                                    "description": "The unique identifier of the machine"
                                }
                            },
                            "required": ["machine_id"]
                        }
                    }
                }
            },
            {
                "toolSpec": {
                    "name": "get_machine_group",
                    "description": "Get comprehensive information about a machine group including all machines, performance metrics, shift schedules, and capacity information.",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "group_id": {
                                    "type": "string",
                                    "description": "The unique identifier of the machine group"
                                }
                            },
                            "required": ["group_id"]
                        }
                    }
                }
            },
            {
                "toolSpec": {
                    "name": "get_production_summary",
                    "description": "Get production summary data and metrics for analysis and reporting.",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "params": {
                                    "type": "object",
                                    "description": "Parameters for filtering production data",
                                    "properties": {
                                        "date_from": {
                                            "type": "string",
                                            "description": "Start date for data range (YYYY-MM-DD)"
                                        },
                                        "date_to": {
                                            "type": "string",
                                            "description": "End date for data range (YYYY-MM-DD)"
                                        },
                                        "machine_ids": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "List of machine IDs to filter by"
                                        }
                                    }
                                }
                            },
                            "required": ["params"]
                        }
                    }
                }
            }
        ]
    
    def _get_intelycx_email_tools(self) -> List[Dict[str, Any]]:
        """Get tool definitions for Intelycx Email API."""
        return [
            {
                "toolSpec": {
                    "name": "send_email",
                    "description": "Send an email with full control over recipients, subject, body, and formatting. Supports HTML content and multiple recipients (TO, CC, BCC).",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "to": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "email": {"type": "string", "description": "Recipient email address"},
                                            "name": {"type": "string", "description": "Recipient name (optional)"}
                                        },
                                        "required": ["email"]
                                    },
                                    "description": "List of email recipients"
                                },
                                "subject": {
                                    "type": "string",
                                    "description": "Email subject line"
                                },
                                "body": {
                                    "type": "string",
                                    "description": "Email body content"
                                },
                                "cc": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "email": {"type": "string"},
                                            "name": {"type": "string"}
                                        },
                                        "required": ["email"]
                                    },
                                    "description": "CC recipients (optional)"
                                },
                                "bcc": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "email": {"type": "string"},
                                            "name": {"type": "string"}
                                        },
                                        "required": ["email"]
                                    },
                                    "description": "BCC recipients (optional)"
                                },
                                "is_html": {
                                    "type": "boolean",
                                    "description": "Whether the body content is HTML format"
                                }
                            },
                            "required": ["to", "subject", "body"]
                        }
                    }
                }
            },
            {
                "toolSpec": {
                    "name": "send_simple_email",
                    "description": "Send a simple email to a single recipient with basic parameters. Ideal for quick notifications and alerts.",
                    "inputSchema": {
                        "json": {
                            "type": "object",
                            "properties": {
                                "to_email": {
                                    "type": "string",
                                    "description": "Recipient email address"
                                },
                                "subject": {
                                    "type": "string",
                                    "description": "Email subject line"
                                },
                                "body": {
                                    "type": "string",
                                    "description": "Email body content"
                                },
                                "to_name": {
                                    "type": "string",
                                    "description": "Recipient name (optional)"
                                },
                                "is_html": {
                                    "type": "boolean",
                                    "description": "Whether the body content is HTML format"
                                }
                            },
                            "required": ["to_email", "subject", "body"]
                        }
                    }
                }
            }
        ]


