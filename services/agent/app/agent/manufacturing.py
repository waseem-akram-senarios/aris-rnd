from .base import BaseAgent, AgentResponse
from typing import Any, Dict, Optional
from ..utils.documents import get_document_content_from_s3
from ..llm.bedrock import BedrockClient
from ..config.settings import load_settings
import logging


class ManufacturingAgent(BaseAgent):
    def __init__(self) -> None:
        self._settings = load_settings()
        self._bedrock = BedrockClient(region=self._settings.BEDROCK_REGION or "us-east-2")
        self._logger = logging.getLogger("agent.manufacturing")
        self._model_id_override: Optional[str] = None
        self._messages: list[dict] = []  # in-connection conversation memory

    async def process_message(self, message: str) -> AgentResponse:
        # Minimal LLM call to Bedrock (no tools yet)
        model_id = self._model_id_override or "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
        self._logger.info(f"Starting ManufacturingAgent with model={model_id} region={self._settings.BEDROCK_REGION}")        

        # Append user message to in-session memory
        self._messages.append({"role": "user", "content": [{"text": message or ""}]})

        text = self._bedrock.converse(
            model_id=model_id,
            messages=self._messages[-20:],
            system=[{"text": "You are ARIS, a helpful manufacturing assistant. Maintain context across the conversation and remember user-provided details such as their name during this session."}],
            temperature=0.1,
        )

        # Append assistant reply to memory
        self._messages.append({"role": "assistant", "content": [{"text": text or ""}]})        
        return AgentResponse(is_final=True, text=text or "", data={})

    def set_runtime_options(self, options: Dict[str, Any]) -> None:
        self._model_id_override = options.get("model_id")

    async def process_document(self, bucket: str, key: str) -> Dict[str, Any]:
        doc = get_document_content_from_s3(bucket, key)
        return {
            "document": {
                "name": doc.name,
                "format": doc.format,
                "source": {"bytes": doc.bytes_data.decode("utf-8", errors="ignore")},
            }
        }


