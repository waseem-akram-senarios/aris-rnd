"""WebSocket observer for plan changes."""

import json
import logging
from typing import Callable, Awaitable, Optional

from .observer import PlanObserver
from .models import ExecutionPlan, create_planning_websocket_message, create_plan_update_websocket_message


class WebSocketPlanObserver(PlanObserver):
    """Observer that sends WebSocket messages when plans are created or updated."""
    
    def __init__(
        self, 
        websocket_send_callback: Callable[[dict], Awaitable[None]],
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize WebSocket plan observer.
        
        Args:
            websocket_send_callback: Async function to send WebSocket messages
            logger: Optional logger instance
        """
        self.send_websocket = websocket_send_callback
        self.logger = logger or logging.getLogger(__name__)
        
        # Track last sent state to prevent duplicate updates
        self._last_plan_state = {}
        self._last_action_states = {}
    
    async def on_plan_created(self, plan: ExecutionPlan) -> None:
        """Send plan_create WebSocket message when a plan is created."""
        try:
            message = create_planning_websocket_message(plan)
            await self.send_websocket(message)
            self.logger.info(f"📤 Sent plan_create for {plan.plan_id} ({len(plan.actions)} actions)")
        except Exception as e:
            self.logger.error(f"❌ Failed to send plan_create message: {e}")
    
    async def on_plan_updated(self, plan: ExecutionPlan) -> None:
        """Send plan_update WebSocket message when a plan is updated."""
        try:
            # Create current state signature to detect actual changes
            current_plan_state = f"{plan.status}"
            current_action_states = {action.id: action.status for action in plan.actions}
            
            # Check if plan or any action status actually changed
            plan_changed = (
                plan.plan_id not in self._last_plan_state or 
                self._last_plan_state[plan.plan_id] != current_plan_state
            )
            
            actions_changed = (
                plan.plan_id not in self._last_action_states or
                self._last_action_states[plan.plan_id] != current_action_states
            )
            
            # Only send update if something actually changed
            if plan_changed or actions_changed:
                message = create_plan_update_websocket_message(plan)
                await self.send_websocket(message)
                
                # Update tracked state
                self._last_plan_state[plan.plan_id] = current_plan_state
                self._last_action_states[plan.plan_id] = current_action_states
                
                self.logger.debug(f"📤 Sent plan_update for {plan.plan_id} (status: {plan.status})")
            else:
                self.logger.debug(f"🔇 Skipped duplicate plan_update for {plan.plan_id}")
                
        except Exception as e:
            self.logger.error(f"❌ Failed to send plan_update message: {e}")
