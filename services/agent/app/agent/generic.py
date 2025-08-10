from .base import BaseAgent, AgentResponse


class GenericAgent(BaseAgent):
    async def process_message(self, message: str) -> AgentResponse:
        reply = f"[generic] You said: {message}"
        return AgentResponse(is_final=True, text=reply, data={})


