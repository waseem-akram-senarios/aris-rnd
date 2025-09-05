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
    
    async def on_plan_created(self, plan: ExecutionPlan) -> None:
        """Send plan_create WebSocket message when a plan is created."""
        try:
            message = create_planning_websocket_message(plan)
            await self.send_websocket(message)
            self.logger.info(f"📤 Sent plan_create message for plan {plan.plan_id}")
        except Exception as e:
            self.logger.error(f"❌ Failed to send plan_create message: {e}")
    
    async def on_plan_updated(self, plan: ExecutionPlan) -> None:
        """Send plan_update WebSocket message when a plan is updated."""
        try:
            message = create_plan_update_websocket_message(plan)
            await self.send_websocket(message)
            self.logger.info(f"📤 Sent plan_update message for plan {plan.plan_id} (status: {plan.status})")
        except Exception as e:
            self.logger.error(f"❌ Failed to send plan_update message: {e}")
