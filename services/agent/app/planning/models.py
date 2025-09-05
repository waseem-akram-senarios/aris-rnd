"""Planning models for agent execution planning and chain-of-thought messaging."""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class ActionType(str, Enum):
    """Types of actions the agent can plan to execute."""
    TOOL_CALL = "tool_call"
    ANALYSIS = "analysis"
    RESPONSE = "response"


@dataclass
class PlannedAction:
    """Represents a single planned action in the execution plan."""
    id: str
    type: ActionType
    name: str
    description: str
    tool_name: Optional[str] = None
    arguments: Optional[Dict[str, Any]] = None
    depends_on: Optional[List[str]] = None  # IDs of actions this depends on
    status: str = "pending"  # pending, starting, in_progress, completed, failed


@dataclass
class ExecutionPlan:
    """Represents the complete execution plan for a user request."""
    plan_id: str
    user_query: str
    summary: str
    actions: List[PlannedAction]
    status: str = "new"  # new, in_progress, error, aborted, completed
    
    def update_action_status(self, action_id: str, status: str) -> bool:
        """Update the status of a specific action."""
        for action in self.actions:
            if action.id == action_id:
                action.status = status
                return True
        return False
    
    def get_action_by_id(self, action_id: str) -> Optional[PlannedAction]:
        """Get an action by its ID."""
        for action in self.actions:
            if action.id == action_id:
                return action
        return None
    
    def get_action_by_tool_name(self, tool_name: str) -> Optional[PlannedAction]:
        """Get the first action that uses a specific tool."""
        for action in self.actions:
            if action.tool_name == tool_name:
                return action
        return None
    
    def update_plan_status(self, status: str) -> None:
        """Update the overall plan status."""
        self.status = status
    
    def is_completed(self) -> bool:
        """Check if all actions are completed."""
        return all(action.status == "completed" for action in self.actions)
    
    def has_failed_actions(self) -> bool:
        """Check if any actions have failed."""
        return any(action.status == "failed" for action in self.actions)
    
    def auto_update_plan_status(self) -> str:
        """Automatically update plan status based on action statuses."""
        if self.has_failed_actions():
            self.status = "error"
        elif self.is_completed():
            self.status = "completed"
        elif any(action.status in ["starting", "in_progress"] for action in self.actions):
            self.status = "in_progress"
        # Keep current status if no changes needed
        return self.status


@dataclass
class ChainOfThoughtMessage:
    """Represents a chain-of-thought progress update during execution."""
    action_id: str
    action_name: str
    status: str  # "starting", "in_progress", "completed", "failed"
    message: str
    details: Optional[Dict[str, Any]] = None


def create_planning_websocket_message(plan: ExecutionPlan) -> Dict[str, Any]:
    """Create a WebSocket message for the execution plan."""
    return {
        "type": "plan_create",
        "data": {
            "plan_id": plan.plan_id,
            "summary": plan.summary,
            "status": plan.status,
            "actions": [
                {
                    "id": action.id,
                    "type": action.type.value,
                    "name": action.name,
                    "description": action.description,
                    "tool_name": action.tool_name,
                    "arguments": action.arguments,
                    "depends_on": action.depends_on,

                    "status": action.status
                }
                for action in plan.actions
            ],

        }
    }


def create_plan_update_websocket_message(plan: ExecutionPlan) -> Dict[str, Any]:
    """Create a WebSocket message for plan execution updates with full plan structure."""
    return {
        "type": "plan_update",
        "data": {
            "plan_id": plan.plan_id,
            "summary": plan.summary,
            "status": plan.status,
            "actions": [
                {
                    "id": action.id,
                    "type": action.type.value,
                    "name": action.name,
                    "description": action.description,
                    "tool_name": action.tool_name,
                    "arguments": action.arguments,
                    "depends_on": action.depends_on,

                    "status": action.status
                }
                for action in plan.actions
            ],

        }
    }
