"""
Database-backed plan manager for ARIS agent.
Handles persistent storage of execution plans and actions.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import select, update, and_, func
from sqlalchemy.dialects.postgresql import insert

from .connection import db_manager
from .models import Chat, Plan, Action
from ..planning.models import ExecutionPlan, ActionType

logger = logging.getLogger(__name__)


class DatabasePlanManager:
    """Database-backed plan manager with PostgreSQL persistence."""
    
    def __init__(self, chat_id: str):
        self.chat_id = chat_id
        self.logger = logger.getChild(f"plan.{chat_id}")
    
    async def store_plan(self, execution_plan: ExecutionPlan) -> None:
        """Store an execution plan and all its actions in the database."""
        
        # Debug logging to trace attribute access
        self.logger.debug(f"🔍 ExecutionPlan type: {type(execution_plan)}")
        self.logger.debug(f"🔍 ExecutionPlan dir: {[attr for attr in dir(execution_plan) if not attr.startswith('_')]}")
        
        self.logger.info(f"📋 Storing plan {execution_plan.plan_id} with {len(execution_plan.actions)} actions")
        
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
                        name=action.name,
                        description=action.description,
                        type=action.type.value,  # Convert enum to string
                        tool_name=action.tool_name,
                        arguments=action.arguments,
                        depends_on=action.depends_on or [],
                        status=action.status,
                        execution_order=i + 1,
                        created_at=datetime.utcnow()
                    )
                    session.add(db_action)
                
                await session.commit()
                self.logger.info(f"✅ Stored plan {execution_plan.plan_id} with {len(execution_plan.actions)} actions")
                
        except Exception as e:
            self.logger.error(f"❌ Failed to store plan {execution_plan.plan_id}: {str(e)}")
            raise
    
    async def update_plan_status(self, plan_id: str, status: str) -> None:
        """Update plan status."""
        
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
                    # Calculate execution duration if we have start time
                    result = await session.execute(
                        select(Plan.started_at).where(Plan.id == plan_id)
                    )
                    started_at = result.scalar_one_or_none()
                    if started_at:
                        duration = (datetime.utcnow() - started_at).total_seconds() * 1000
                        update_values['execution_duration_ms'] = int(duration)
                
                await session.execute(
                    update(Plan)
                    .where(Plan.id == plan_id)
                    .values(**update_values)
                )
                await session.commit()
                
                self.logger.debug(f"📋 Updated plan {plan_id} status: {status}")
                
        except Exception as e:
            self.logger.error(f"❌ Failed to update plan status {plan_id}: {str(e)}")
            raise
    
    async def update_action_status(
        self, 
        action_id: str, 
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Update action status and result."""
        
        try:
            async with db_manager.get_session() as session:
                # Update action status and timing
                update_values = {
                    'status': status,
                    'updated_at': datetime.utcnow()
                }
                
                if status == 'starting':
                    update_values['started_at'] = datetime.utcnow()
                elif status in ['completed', 'failed', 'cancelled']:
                    update_values['completed_at'] = datetime.utcnow()
                    # Calculate execution duration if we have start time
                    result_query = await session.execute(
                        select(Action.started_at).where(Action.id == action_id)
                    )
                    started_at = result_query.scalar_one_or_none()
                    if started_at:
                        duration = (datetime.utcnow() - started_at).total_seconds() * 1000
                        update_values['execution_duration_ms'] = int(duration)
                
                if result is not None:
                    update_values['result'] = result
                
                if error_message is not None:
                    update_values['error_message'] = error_message
                
                await session.execute(
                    update(Action)
                    .where(Action.id == action_id)
                    .values(**update_values)
                )
                
                # Update plan action counters
                if status in ['completed', 'failed']:
                    await self._update_plan_counters(session, action_id)
                
                await session.commit()
                
                self.logger.debug(f"🔧 Updated action {action_id} status: {status}")
                
        except Exception as e:
            self.logger.error(f"❌ Failed to update action status {action_id}: {str(e)}")
            raise
    
    async def get_plan(self, plan_id: str) -> Optional[ExecutionPlan]:
        """Retrieve a plan from the database and convert to ExecutionPlan object."""
        
        try:
            async with db_manager.get_session() as session:
                # Get plan with actions
                plan_result = await session.execute(
                    select(Plan).where(Plan.id == plan_id)
                )
                plan = plan_result.scalar_one_or_none()
                
                if plan is None:
                    return None
                
                # Get actions for this plan
                actions_result = await session.execute(
                    select(Action)
                    .where(Action.plan_id == plan_id)
                    .order_by(Action.execution_order)
                )
                actions = actions_result.scalars().all()
                
                # Convert to ExecutionPlan object
                from ..planning.models import PlanAction
                
                plan_actions = []
                for action in actions:
                    plan_action = PlanAction(
                        id=action.id,
                        name=action.name,
                        description=action.description,
                        type=ActionType(action.type),
                        tool_name=action.tool_name,
                        arguments=action.arguments,
                        depends_on=action.depends_on or [],
                        status=action.status
                    )
                    plan_actions.append(plan_action)
                
                execution_plan = ExecutionPlan(
                    id=plan.id,
                    summary=plan.summary,
                    status=plan.status,
                    actions=plan_actions,
                    user_query=plan.user_query,
                    model_id=plan.model_id,
                    temperature=float(plan.temperature) if plan.temperature else None,
                    metadata=plan.extra_data or {}
                )
                
                return execution_plan
                
        except Exception as e:
            self.logger.error(f"❌ Failed to get plan {plan_id}: {str(e)}")
            raise
    
    async def get_active_plan(self) -> Optional[ExecutionPlan]:
        """Get the currently active plan for this chat."""
        
        try:
            async with db_manager.get_session() as session:
                result = await session.execute(
                    select(Plan.id)
                    .where(
                        and_(
                            Plan.chat_id == self.chat_id,
                            Plan.status.in_(['new', 'in_progress'])
                        )
                    )
                    .order_by(Plan.created_at.desc())
                    .limit(1)
                )
                
                plan_id = result.scalar_one_or_none()
                if plan_id:
                    return await self.get_plan(plan_id)
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Failed to get active plan: {str(e)}")
            raise
    
    async def _update_plan_counters(self, session, action_id: str) -> None:
        """Update plan completion counters based on action status."""
        
        # Get the plan_id for this action
        result = await session.execute(
            select(Action.plan_id, Action.status).where(Action.id == action_id)
        )
        action_data = result.fetchone()
        
        if action_data is None:
            return
        
        plan_id, action_status = action_data
        
        # Count completed and failed actions for this plan
        counts_result = await session.execute(text("""
            SELECT 
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed,
                COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed
            FROM actions 
            WHERE plan_id = :plan_id
        """), {"plan_id": plan_id})
        
        counts = counts_result.fetchone()
        completed_count, failed_count = counts
        
        # Update plan counters
        await session.execute(
            update(Plan)
            .where(Plan.id == plan_id)
            .values(
                completed_actions=completed_count,
                failed_actions=failed_count
            )
        )
    
    async def _ensure_chat_exists(self, session) -> None:
        """Ensure the chat record exists in the database."""
        
        # Check if chat exists
        result = await session.execute(
            select(Chat.id).where(Chat.id == self.chat_id)
        )
        
        if result.scalar_one_or_none() is None:
            # Create chat record
            chat = Chat(
                id=self.chat_id,
                user_id="unknown",  # Will be updated when we have user info
                agent_type="manufacturing",
                status="active"
            )
            session.add(chat)
            await session.flush()  # Ensure chat is created before plans
            self.logger.info(f"📝 Created new chat record: {self.chat_id}")
