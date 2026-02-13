import os
from .manufacturing import ManufacturingAgent
from .generic import GenericAgent
from .base import BaseAgent
from ..config.settings import Settings


class AgentFactory:
    def __init__(self, settings: Settings):
        self.settings = settings

    def create(self) -> BaseAgent:
        agent_type = (self.settings.AGENT_TYPE or "manufacturing").lower()
        if agent_type == "manufacturing":
            return ManufacturingAgent()
        return GenericAgent()


