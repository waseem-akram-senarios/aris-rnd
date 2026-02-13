from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class AgentResponse:
    is_final: bool
    text: str
    data: Optional[Dict[str, Any]] = None


class BaseAgent:
    async def process_message(self, message: str) -> AgentResponse:  # pragma: no cover - to be implemented by subclasses
        raise NotImplementedError

    def set_runtime_options(self, options: Dict[str, Any]) -> None:
        """Pass per-request options such as model_id, temperature, etc."""
        # Default: ignore
        return

    def get_recent_messages(self) -> list[Dict[str, Any]]:
        """Return a small window of recent conversation messages for guardrail context.

        Default implementation returns empty. Agents that keep in-session memory
        should override to provide recent messages in Bedrock-friendly format.
        """
        return []


