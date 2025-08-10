from .base import BaseAgent, AgentResponse
from typing import Any, Dict, Optional
from ..utils.documents import get_document_content_from_s3
from ..llm.bedrock import BedrockClient
from ..config.settings import load_settings


class ManufacturingAgent(BaseAgent):
    def __init__(self) -> None:
        self._settings = load_settings()
        self._bedrock = BedrockClient(region=self._settings.BEDROCK_REGION or "us-east-2")

    async def process_message(self, message: str) -> AgentResponse:
        # Minimal LLM call to Bedrock (no tools yet)
        model_id = "us.anthropic.claude-3-7-sonnet-20250219-v1:0"
        text = self._bedrock.converse(
            model_id=model_id,
            messages=[{"role": "user", "content": [{"text": message or ""}]}],
            system=[{"text": "You are ARIS, a helpful manufacturing assistant."}],
            temperature=0.1,
        )
        return AgentResponse(is_final=True, text=text or "", data={})

    async def process_document(self, bucket: str, key: str) -> Dict[str, Any]:
        doc = get_document_content_from_s3(bucket, key)
        return {
            "document": {
                "name": doc.name,
                "format": doc.format,
                "source": {"bytes": doc.bytes_data.decode("utf-8", errors="ignore")},
            }
        }


