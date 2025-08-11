from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging

from ..llm.bedrock import BedrockClient
from ..config.settings import Settings


logger = logging.getLogger(__name__)


class GuardrailService:
    """Provides lightweight guardrails such as relevance checking.

    This mirrors the old agent's behavior where, when guardrails are enabled,
    a quick LLM-based check determines whether the question is relevant to the
    manufacturing domain and conversation context. If not, the request is blocked.
    """

    def __init__(self, settings: Settings) -> None:
        region = settings.BEDROCK_REGION or settings.REGION or "us-east-2"
        self._bedrock = BedrockClient(region=region)
        self._logger = logging.getLogger("security.guardrails")

    def is_relevant(self, question: str, history_messages: Optional[List[Dict[str, Any]]] = None) -> bool:
        """Return True if the question is relevant; False otherwise.

        Falls back to allowing the request (True) on any errors, to avoid blocking
        valid flows due to transient issues.
        """
        try:
            # Trim history to keep prompt small
            safe_history: List[Dict[str, Any]] = (history_messages or [])[-5:]
            # Convert to a compact text form to avoid extra tokens
            history_text_parts: List[str] = []
            for msg in safe_history:
                role = msg.get("role", "user")
                content_list = msg.get("content", [])
                text_chunks = []
                for c in content_list:
                    if isinstance(c, dict) and "text" in c:
                        t = str(c.get("text", ""))
                        if t:
                            text_chunks.append(t[:500])
                if text_chunks:
                    history_text_parts.append(f"{role}: " + " ".join(text_chunks))
            history_text = "\n".join(history_text_parts)[-4000:]

            system_prompt = (
                "You are an assistant that strictly returns a single boolean token.\n"
                "Return True if the user query is relevant to manufacturing, machinery, maintenance,\n"
                "engineering, equipment, factory operations, documents/manuals related to those,\n"
                "or the company's manufacturing context. Return False for topics like pop culture,\n"
                "personal opinions, politics, religion, or unrelated general knowledge.\n"
                "Do not add any explanation. Return exactly one of: True or False."
            )

            user_prompt = f"""
<history>
{history_text}
</history>

<query>
{question}
</query>

Answer with exactly one token: True or False
""".strip()

            # Use a conservative, fast model when possible (same default as agent if not provided)
            # We rely on BedrockClient which chooses model in higher layers; here we pass messages directly
            text_response = self._bedrock.converse(
                model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
                messages=[{"role": "user", "content": [{"text": user_prompt}]}],
                system=[{"text": system_prompt}],
                temperature=0.0,
            )

            normalized = (text_response or "").strip().lower()
            if normalized.startswith("true"):
                return True
            if normalized.startswith("false"):
                return False

            # If model did not comply, do a simple keyword heuristic as fallback
            keywords = [
                "manufactur", "machine", "equipment", "oee", "maintenance", "line", "cell",
                "molding", "welding", "cutting", "ticket", "shift", "part", "scrap",
                "document", "manual",
            ]
            lowered = (question or "").lower()
            heuristic = any(k in lowered for k in keywords)
            self._logger.warning("Guardrail LLM non-boolean output; using heuristic=%s", heuristic)
            return heuristic
        except Exception as exc:
            self._logger.exception("Guardrail relevance check failed: %s", exc)
            # Default allow on failure
            return True


def get_guardrail_message() -> Dict[str, Any]:
    return {
        "text": (
            "Guardrail activated. I can help with manufacturing equipment, processes, and related topics. "
            "Please ask a question relevant to your manufacturing context."
        ),
        "data": {},
    }



