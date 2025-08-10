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


