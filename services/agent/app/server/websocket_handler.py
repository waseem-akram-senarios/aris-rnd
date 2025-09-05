import json
import logging
import asyncio
from aiohttp import web, WSMsgType
from typing import Any, Dict
import contextlib

from ..agent.factory import AgentFactory
from ..config.settings import Settings
from ..security.cognito import CognitoAuthService
from ..security.guardrails import GuardrailService, get_guardrail_message
from ..planning import ExecutionPlan, ChainOfThoughtMessage, create_planning_websocket_message, create_plan_update_websocket_message
from ..planning import PlanManager, WebSocketPlanObserver


logger = logging.getLogger(__name__)


class WebSocketHandler:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.auth_service = CognitoAuthService(settings)
        self.agent_factory = AgentFactory(settings)
        self.guardrails = GuardrailService(settings)

    async def handle_connection(self, request: web.Request) -> web.StreamResponse:
        try:
            user_info = await self.auth_service.verify_request(request)
        except web.HTTPUnauthorized:
            raise
        except Exception as exc:
            logger.exception("Auth verification failed: %s", exc)
            raise web.HTTPUnauthorized()

        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)

        agent = self.agent_factory.create()
        stop_event = asyncio.Event()
        
        # Create plan manager with WebSocket observer
        plan_manager = PlanManager(logger)
        
        # WebSocket send function for the observer
        async def send_websocket_message(message: dict) -> None:
            try:
                await ws.send_json(message)
                logger.info("WSS OUT: %s", json.dumps(message))
            except Exception as e:
                logger.warning(f"Failed to send WebSocket message: {e}")
        
        # Add WebSocket observer to plan manager
        websocket_observer = WebSocketPlanObserver(send_websocket_message, logger)
        plan_manager.add_observer(websocket_observer)
        
        # Set up progress callback for chain of thought messages (legacy)
        async def send_progress(message: str) -> None:
            progress_msg = {
                "message": message,
                "type": "chain_of_thought",
            }
            try:
                await ws.send_json(progress_msg)
                logger.info("WSS OUT: %s", json.dumps(progress_msg))
            except Exception as e:
                logger.warning(f"Failed to send progress message: {e}")
        
        # Set up planning callback for execution plans
        async def send_plan(plan: ExecutionPlan) -> None:
            planning_msg = create_planning_websocket_message(plan)
            try:
                await ws.send_json(planning_msg)
                logger.info("WSS OUT: %s", json.dumps(planning_msg))
            except Exception as e:
                logger.warning(f"Failed to send planning message: {e}")
        
        # Set up plan update callback for execution updates
        async def send_plan_update(plan: ExecutionPlan) -> None:
            plan_msg = create_plan_update_websocket_message(plan)
            try:
                await ws.send_json(plan_msg)
                logger.info("WSS OUT: %s", json.dumps(plan_msg))
            except Exception as e:
                logger.warning(f"Failed to send plan update message: {e}")
        
        # Set the callbacks on the agent
        if hasattr(agent, 'set_progress_callback'):
            agent.set_progress_callback(send_progress)
        if hasattr(agent, 'set_plan_manager'):
            agent.set_plan_manager(plan_manager)
        # Keep legacy callbacks for backward compatibility
        if hasattr(agent, 'set_planning_callback'):
            agent.set_planning_callback(send_plan)
        if hasattr(agent, 'set_plan_update_callback'):
            agent.set_plan_update_callback(send_plan_update)

        async def _ping_loop() -> None:
            try:
                while not stop_event.is_set():
                    try:
                        await ws.send_json({"type": "ping"})
                    except Exception:
                        break
                    await asyncio.sleep(5)
            except asyncio.CancelledError:
                pass

        ping_task = asyncio.create_task(_ping_loop())

        def _truncate(text: str, limit: int = 2000) -> str:
            return text if len(text) <= limit else text[:limit] + "... (truncated)"

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        payload = json.loads(msg.data)
                    except json.JSONDecodeError:
                        await ws.send_json({"type": "error", "message": "invalid_json"})
                        continue

                    # Log incoming message (sanitized/truncated)
                    try:
                        logger.info("WSS IN: %s", _truncate(json.dumps({k: v for k, v in payload.items() if k.lower() != "authorization"})))
                    except Exception:
                        logger.info("WSS IN: <unserializable payload>")

                    # Accept both {"message": ...} and old format {"action":"agent", "question": ...};
                    # pass model_id to agent runtime options
                    msg_text = payload.get("message")
                    if msg_text is None and payload.get("action") == "agent":
                        msg_text = payload.get("question", "")
                    if msg_text is None:
                        msg_text = ""

                    # Optional document handling: { doc_bucket, doc_key }
                    if payload.get("doc_bucket") and payload.get("doc_key"):
                        try:
                            # Pass the message to process_document so it can inject file content
                            doc_resp = await agent.process_document(
                                payload["doc_bucket"], 
                                payload["doc_key"],
                                msg_text  # Pass the message for context injection
                            )  # type: ignore[attr-defined]
                            
                            # Send document processing notification
                            outgoing_doc = {
                                "type": "doc", 
                                "data": {
                                    "document": {
                                        "name": doc_resp["document"]["name"], 
                                        "format": doc_resp["document"].get("format", "unknown"),
                                        "type": doc_resp["document"].get("type", "text"),
                                        "metadata": doc_resp["document"].get("metadata", {})
                                    }
                                }
                            }
                            await ws.send_json(outgoing_doc)
                            logger.info("WSS OUT: %s", _truncate(json.dumps(outgoing_doc)))
                        except Exception as exc:
                            err = {"type": "error", "message": f"doc_processing_failed: {exc}"}
                            await ws.send_json(err)
                            logger.info("WSS OUT: %s", _truncate(json.dumps(err)))

                    # Extract model/config knobs
                    rag_params: Dict[str, Any] = {}
                    try:
                        rag_params = payload.get("rag_params", {}) or {}
                    except Exception:
                        rag_params = {}

                    model_params = {}
                    try:
                        model_params = rag_params.get("model_params", {}) or {}
                    except Exception:
                        model_params = {}

                    model_id = payload.get("model_id") or model_params.get("model_id")
                    temperature = None
                    try:
                        temperature = model_params.get("temperature")
                    except Exception:
                        temperature = None

                    # Optional search toggles from rag_params or top-level payload
                    def _get_bool(path_default_false: Any) -> bool:
                        try:
                            return bool(path_default_false)
                        except Exception:
                            return False

                    deep_search = False
                    web_search = False
                    try:
                        search_block = rag_params.get("search", {}) or {}
                        deep_search = _get_bool(search_block.get("deep_search", rag_params.get("deep_search", payload.get("deep_search"))))
                        web_search = _get_bool(search_block.get("web_search", rag_params.get("web_search", payload.get("web_search"))))
                    except Exception:
                        deep_search = False
                        web_search = False

                    # Guardrails flag (computed here for logging as well)
                    try:
                        guardrails_enabled = bool(rag_params.get("guardrails", False))
                    except Exception:
                        guardrails_enabled = False

                    # Log planning configuration snapshot before any planning/guardrails
                    try:
                        planning_config = {
                            "agent_type": self.settings.AGENT_TYPE,
                            "region": self.settings.REGION,
                            "bedrock_region": self.settings.BEDROCK_REGION,
                            "model_id": model_id,
                            "temperature": temperature,
                            "guardrails": guardrails_enabled,
                            "deep_search": deep_search,
                            "web_search": web_search,
                        }
                        logger.info("Planning config: %s", json.dumps(planning_config))
                    except Exception:
                        logger.info("Planning config: <unserializable>")

                    # Forward runtime options to agent
                    try:
                        agent.set_runtime_options({"model_id": model_id, "temperature": temperature})
                    except Exception:
                        pass

                    # Emit early chain-of-thought style update for better UX
                    outgoing_think = {
                        "message": "Thinking...",
                        "type": "chain_of_thought",
                    }
                    await ws.send_json(outgoing_think)
                    logger.info("WSS OUT: %s", json.dumps(outgoing_think))

                    # Guardrails: optionally block irrelevant queries when requested (flag already computed)

                    if guardrails_enabled:
                        try:
                            recent_history = []
                            try:
                                recent_history = getattr(agent, "get_recent_messages", lambda: [])()
                            except Exception:
                                recent_history = []
                            is_rel = self.guardrails.is_relevant(msg_text or "", recent_history)
                            if not is_rel:
                                gr_msg = get_guardrail_message()
                                final_msg = {"message": gr_msg["text"], "data": gr_msg.get("data", {}), "type": "message", "action": "close"}
                                await ws.send_json(final_msg)
                                logger.info("WSS OUT: %s", _truncate(json.dumps(final_msg)))
                                continue
                        except Exception as exc:
                            logger.exception("Guardrail check failed (allow by default): %s", exc)

                    # Process message and send final response only (no streaming)
                    text = (await agent.process_message(msg_text)).text
                    
                    final_msg = {
                        "message": text,
                        "data": {},
                        "type": "message",
                        "action": "close",
                    }
                    await ws.send_json(final_msg)
                    logger.info("WSS OUT: %s", _truncate(json.dumps({**final_msg, "message": _truncate(text, 500)})))
                elif msg.type == WSMsgType.ERROR:
                    logger.error("ws connection closed with exception %s", ws.exception())
                    break
        finally:
            stop_event.set()
            ping_task.cancel()
            with contextlib.suppress(Exception):
                await ping_task
            await ws.close()
            return ws


