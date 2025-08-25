from .base import BaseAgent, AgentResponse
from typing import Any, Dict, Optional
from pathlib import Path
from ..utils.documents import get_document_content_from_s3
from ..utils.file_handlers import FileProcessor
from ..llm.bedrock import BedrockClient
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

        text = self._bedrock.converse(
            model_id=model_id,
            messages=self._messages[-20:],
            system=[{"text": "You are ARIS, a helpful manufacturing assistant. Maintain context across the conversation and remember user-provided details such as their name during this session. When documents are provided, analyze them and answer questions based on their content."}],
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


