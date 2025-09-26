"""
Unified Plan Manager - Single source of truth for all plan and action operations.

This manager handles:
- Plan creation and storage in database
- Action status updates in database  
- WebSocket notifications to UI
- Plan retrieval and state management
"""

import logging
from typing import Optional, Dict, Any, Callable, Awaitable
from datetime import datetime
from sqlalchemy import select, update, and_
from sqlalchemy.dialects.postgresql import insert

from .connection import db_manager
from .models import Plan, Action, Chat
from ..planning.models import ExecutionPlan, PlannedAction, ActionType
from .serialization import serialize_for_database

logger = logging.getLogger(__name__)


class UnifiedPlanManager:
    """Centralized manager for all plan and action operations."""
    
    def __init__(self, chat_id: str):
        self.chat_id = chat_id
        self.logger = logger.getChild(f"unified_plan.{chat_id}")
        
        # WebSocket callback for UI notifications
        self._websocket_callback: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None
    
    def set_websocket_callback(self, callback: Callable[[str, Dict[str, Any]], Awaitable[None]]) -> None:
        """Set callback for sending WebSocket notifications to UI."""
        self._websocket_callback = callback
    
    # ============================================================================
    # PLAN LIFECYCLE MANAGEMENT
    # ============================================================================
    
    async def create_plan(self, execution_plan: ExecutionPlan) -> str:
        """Create a new plan in database and send UI notification."""
        
        self.logger.info(f"📋 Creating plan {execution_plan.plan_id} with {len(execution_plan.actions)} actions")
        
        try:
            async with db_manager.get_session() as session:
                # Ensure chat exists
                await self._ensure_chat_exists(session)
                
                # Store the plan (handle missing attributes gracefully)
                plan = Plan(
                    id=execution_plan.plan_id,
                    chat_id=self.chat_id,
                    summary=execution_plan.summary,
                    status=execution_plan.status,
                    user_query=execution_plan.user_query or "",
                    model_id=getattr(execution_plan, 'model_id', None),
                    temperature=getattr(execution_plan, 'temperature', None),
                    total_actions=len(execution_plan.actions),
                    completed_actions=0,
                    failed_actions=0,
                    created_at=datetime.utcnow(),
                    extra_data=getattr(execution_plan, 'metadata', {}) or {}
                )
                session.add(plan)
                
                # Store all actions
                for i, action in enumerate(execution_plan.actions):
                    db_action = Action(
                        id=action.id,
                        plan_id=execution_plan.plan_id,
                        type=action.type.value,
                        name=action.name,
                        description=action.description,
                        tool_name=action.tool_name,
                        arguments=serialize_for_database(action.arguments) if action.arguments else None,
                        depends_on=action.depends_on or [],
                        status=action.status,
                        execution_order=i + 1,
                        created_at=datetime.utcnow()
                    )
                    session.add(db_action)
                
                await session.commit()
                self.logger.info(f"✅ Created plan {execution_plan.plan_id} with {len(execution_plan.actions)} actions in database")
                
                # Send UI notification
                await self._send_plan_create_notification(execution_plan)
                
                return execution_plan.plan_id
                
        except Exception as e:
            self.logger.error(f"❌ Failed to create plan {execution_plan.plan_id}: {str(e)}")
            raise
    
    async def get_plan(self, plan_id: str) -> Optional[ExecutionPlan]:
        """Retrieve plan from database and convert to ExecutionPlan object."""
        
        try:
            async with db_manager.get_session() as session:
                # Get plan
                plan_result = await session.execute(
                    select(Plan).where(Plan.id == plan_id)
                )
                plan_row = plan_result.scalar_one_or_none()
                
                if not plan_row:
                    return None
                
                # Get actions
                actions_result = await session.execute(
                    select(Action).where(Action.plan_id == plan_id).order_by(Action.execution_order)
                )
                action_rows = actions_result.scalars().all()
                
                # Convert to ExecutionPlan
                actions = []
                for action_row in action_rows:
                    action = PlannedAction(
                        id=action_row.id,
                        type=ActionType(action_row.type),
                        name=action_row.name,
                        description=action_row.description,
                        tool_name=action_row.tool_name,
                        arguments=action_row.arguments,
                        depends_on=action_row.depends_on,
                        status=action_row.status
                    )
                    actions.append(action)
                
                execution_plan = ExecutionPlan(
                    plan_id=plan_row.id,
                    user_query=plan_row.user_query,
                    summary=plan_row.summary,
                    actions=actions,
                    status=plan_row.status
                )
                
                return execution_plan
                
        except Exception as e:
            self.logger.error(f"❌ Failed to get plan {plan_id}: {str(e)}")
            return None
    
    async def update_plan_status(self, plan_id: str, status: str) -> None:
        """Update plan status in database and send UI notification."""
        
        try:
            async with db_manager.get_session() as session:
                # Update plan status and timing
                update_values = {
                    'status': status,
                    'updated_at': datetime.utcnow()
                }
                
                if status == 'in_progress':
                    update_values['started_at'] = datetime.utcnow()
                elif status in ['completed', 'failed', 'cancelled']:
                    update_values['completed_at'] = datetime.utcnow()
                
                stmt = update(Plan).where(Plan.id == plan_id).values(**update_values)
                await session.execute(stmt)
                await session.commit()
                
                self.logger.info(f"✅ Updated plan {plan_id} status to {status}")
                
                # Send UI notification
                await self._send_plan_update_notification(plan_id)
                
        except Exception as e:
            self.logger.error(f"❌ Failed to update plan status: {str(e)}")
            raise
    
    async def update_plan(self, plan_data: Dict[str, Any]) -> None:
        """Update plan (compatibility method for WebSocket callbacks)."""
        plan_id = plan_data.get("plan_id")
        status = plan_data.get("status") 
        
        if plan_id and status:
            await self.update_plan_status(plan_id, status)
    
    # ============================================================================
    # ACTION MANAGEMENT
    # ============================================================================
    
    async def update_action_status(self, plan_id: str, action_id: str, status: str) -> None:
        """Update action status in database and send UI notification."""
        
        try:
            async with db_manager.get_session() as session:
                # Update action status
                stmt = update(Action).where(
                    and_(
                        Action.plan_id == plan_id,
                        Action.id == action_id
                    )
                ).values(
                    status=status
                )
                
                await session.execute(stmt)
                await session.commit()
                
                # Send UI notification (only log if it fails)
                await self._send_plan_update_notification(plan_id)
                
        except Exception as e:
            self.logger.error(f"❌ Failed to update action status: {str(e)}")
            raise
    
    async def get_action(self, plan_id: str, action_id: str) -> Optional[PlannedAction]:
        """Get specific action from database."""
        
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    select(Action).where(
                        and_(
                            Action.plan_id == plan_id,
                            Action.id == action_id
                        )
                    )
                )
                action_row = result.scalar_one_or_none()
                
                if not action_row:
                    return None
                
                return PlannedAction(
                    id=action_row.id,
                    type=ActionType(action_row.type),
                    name=action_row.name,
                    description=action_row.description,
                    tool_name=action_row.tool_name,
                    arguments=action_row.arguments,
                    depends_on=action_row.depends_on,
                    status=action_row.status
                )
                
        except Exception as e:
            self.logger.error(f"❌ Failed to get action {action_id}: {str(e)}")
            return None
    
    # ============================================================================
    # WEBSOCKET NOTIFICATIONS
    # ============================================================================
    
    async def _send_plan_create_notification(self, execution_plan: ExecutionPlan) -> None:
        """Send plan_create WebSocket notification to UI."""
        
        if not self._websocket_callback:
            return
        
        try:
            # Convert plan to UI format
            plan_data = {
                "plan_id": execution_plan.plan_id,
                "summary": execution_plan.summary,
                "status": execution_plan.status,
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
                    for action in execution_plan.actions
                ]
            }
            
            await self._websocket_callback("plan_create", plan_data)
            self.logger.debug(f"📤 Sent plan_create notification for {execution_plan.plan_id}")
            
        except Exception as e:
            self.logger.warning(f"Failed to send plan_create notification: {e}")
    
    async def _send_plan_update_notification(self, plan_id: str) -> None:
        """Send plan_update WebSocket notification to UI based on current database state."""
        
        if not self._websocket_callback:
            return
        
        try:
            # Read current plan state from database
            execution_plan = await self.get_plan(plan_id)
            if not execution_plan:
                self.logger.warning(f"Cannot send update notification - plan {plan_id} not found in database")
                return
            
            # Convert plan to UI format
            plan_data = {
                "plan_id": execution_plan.plan_id,
                "summary": execution_plan.summary,
                "status": execution_plan.status,
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
                    for action in execution_plan.actions
                ]
            }
            
            await self._websocket_callback("plan_update", plan_data)
            self.logger.debug(f"📤 Sent plan_update notification for {plan_id}")
            
        except Exception as e:
            self.logger.warning(f"Failed to send plan_update notification: {e}")
    
    # ============================================================================
    # UTILITY METHODS
    # ============================================================================
    
    async def _ensure_chat_exists(self, session) -> None:
        """Ensure the chat record exists in the database."""
        
        # Check if chat exists
        result = await session.execute(
            select(Chat).where(Chat.id == self.chat_id)
        )
        existing_chat = result.scalar_one_or_none()
        
        if not existing_chat:
            # Create new chat record
            new_chat = Chat(
                id=self.chat_id,
                user_id="unknown",  # Will be updated later
                agent_type="manufacturing",
                created_at=datetime.utcnow(),
                last_activity_at=datetime.utcnow(),
                extra_data={}
            )
            session.add(new_chat)
            self.logger.info(f"📝 Created new chat record: {self.chat_id}")
    
    async def get_plan_statistics(self, plan_id: str) -> Dict[str, Any]:
        """Get plan execution statistics."""
        
        try:
            async with db_manager.get_session() as session:
                # Get action counts by status
                result = await session.execute(
                    select(Action.status, Action.id).where(Action.plan_id == plan_id)
                )
                actions = result.all()
                
                stats = {
                    "total_actions": len(actions),
                    "pending": len([a for a in actions if a.status == "pending"]),
                    "in_progress": len([a for a in actions if a.status == "in_progress"]),
                    "completed": len([a for a in actions if a.status == "completed"]),
                    "failed": len([a for a in actions if a.status == "failed"])
                }
                
                return stats
                
        except Exception as e:
            self.logger.error(f"❌ Failed to get plan statistics: {str(e)}")
            return {}
