"""Plan observer system for tracking plan creation and updates."""

from abc import ABC, abstractmethod
from typing import List, Optional
import logging

from .models import ExecutionPlan


class PlanObserver(ABC):
    """Abstract base class for plan observers."""
    
    @abstractmethod
    async def on_plan_created(self, plan: ExecutionPlan) -> None:
        """Called when a new plan is created."""
        pass
    
    @abstractmethod
    async def on_plan_updated(self, plan: ExecutionPlan) -> None:
        """Called when an existing plan is updated."""
        pass


class PlanManager:
    """Manages execution plans and notifies observers of changes."""
    
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger(__name__)
        self._observers: List[PlanObserver] = []
        self._current_plan: Optional[ExecutionPlan] = None
    
    def add_observer(self, observer: PlanObserver) -> None:
        """Add a plan observer."""
        self._observers.append(observer)
        self.logger.info(f"📡 Added plan observer: {observer.__class__.__name__}")
    
    def remove_observer(self, observer: PlanObserver) -> None:
        """Remove a plan observer."""
        if observer in self._observers:
            self._observers.remove(observer)
            self.logger.info(f"📡 Removed plan observer: {observer.__class__.__name__}")
    
    async def create_plan(self, plan: ExecutionPlan) -> None:
        """Create a new plan and notify observers."""
        self._current_plan = plan
        self.logger.info(f"📋 Created new plan: {plan.plan_id} (status: {plan.status})")
        
        # Notify all observers
        for observer in self._observers:
            try:
                await observer.on_plan_created(plan)
            except Exception as e:
                self.logger.error(f"❌ Error notifying observer {observer.__class__.__name__}: {e}")
    
    async def update_plan(self, plan: ExecutionPlan) -> None:
        """Update an existing plan and notify observers."""
        if self._current_plan and self._current_plan.plan_id == plan.plan_id:
            self._current_plan = plan
            self.logger.info(f"📋 Updated plan: {plan.plan_id} (status: {plan.status})")
            
            # Notify all observers
            for observer in self._observers:
                try:
                    await observer.on_plan_updated(plan)
                except Exception as e:
                    self.logger.error(f"❌ Error notifying observer {observer.__class__.__name__}: {e}")
        else:
            self.logger.warning(f"⚠️ Attempted to update unknown plan: {plan.plan_id}")
    
    async def update_action_status(self, action_id: str, status: str) -> None:
        """Update an action status and notify observers."""
        if self._current_plan:
            if self._current_plan.update_action_status(action_id, status):
                # Auto-update plan status based on actions
                self._current_plan.auto_update_plan_status()
                await self.update_plan(self._current_plan)
            else:
                self.logger.warning(f"⚠️ Action {action_id} not found in current plan")
        else:
            self.logger.warning("⚠️ No current plan to update action status")
    
    async def update_plan_status(self, status: str) -> None:
        """Update the plan status and notify observers."""
        if self._current_plan:
            self._current_plan.update_plan_status(status)
            await self.update_plan(self._current_plan)
        else:
            self.logger.warning("⚠️ No current plan to update status")
    
    def get_current_plan(self) -> Optional[ExecutionPlan]:
        """Get the current plan."""
        return self._current_plan
    
    def should_create_new_plan(self) -> bool:
        """Check if a new plan should be created."""
        if not self._current_plan:
            return True
        
        # Create new plan if current one is finished
        return self._current_plan.status in ["completed", "failed", "cancelled"]
