from .base import BaseAgent, AgentResponse
from typing import Any, Dict
from ..utils.documents import get_document_content_from_s3


class ManufacturingAgent(BaseAgent):
    async def process_message(self, message: str) -> AgentResponse:
        # Minimal echo behavior; document handling via special directive
        # Expected payload format will be handled at handler level; this agent only processes strings
        reply = f"[manufacturing] You said: {message}"
        return AgentResponse(is_final=True, text=reply, data={})

    async def process_document(self, bucket: str, key: str) -> Dict[str, Any]:
        doc = get_document_content_from_s3(bucket, key)
        return {
            "document": {
                "name": doc.name,
                "format": doc.format,
                "source": {"bytes": doc.bytes_data.decode("utf-8", errors="ignore")},
            }
        }


