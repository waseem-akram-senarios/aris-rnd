import json
import logging
import asyncio
from aiohttp import web, WSMsgType
from typing import Any, Dict
import contextlib

from ..agent.factory import AgentFactory
from ..config.settings import Settings
from ..security.cognito import CognitoAuthService


logger = logging.getLogger(__name__)


class WebSocketHandler:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.auth_service = CognitoAuthService(settings)
        self.agent_factory = AgentFactory(settings)

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

                    # Optional document handling: { doc_bucket, doc_key }
                    if payload.get("doc_bucket") and payload.get("doc_key"):
                        try:
                            doc_resp = await agent.process_document(payload["doc_bucket"], payload["doc_key"])  # type: ignore[attr-defined]
                            outgoing_doc = {"type": "doc", "data": {"document": {"name": doc_resp["document"]["name"], "format": doc_resp["document"]["format"]}}}
                            await ws.send_json(outgoing_doc)
                            logger.info("WSS OUT: %s", _truncate(json.dumps(outgoing_doc)))
                        except Exception as exc:
                            err = {"type": "error", "message": f"doc_processing_failed: {exc}"}
                            await ws.send_json(err)
                            logger.info("WSS OUT: %s", _truncate(json.dumps(err)))

                    # Accept both {"message": ...} and old format {"action":"agent", "question": ...};
                    # pass model_id to agent runtime options
                    msg_text = payload.get("message")
                    if msg_text is None and payload.get("action") == "agent":
                        msg_text = payload.get("question", "")
                    if msg_text is None:
                        msg_text = ""

                    model_id = payload.get("model_id") or payload.get("rag_params", {}).get("model_params", {}).get("model_id")
                    try:
                        agent.set_runtime_options({"model_id": model_id})
                    except Exception:
                        pass

                    # Emit early chain-of-thought style update for better UX
                    outgoing_think = {
                        "message": "Thinking...",
                        "type": "chain_of_thought",
                    }
                    await ws.send_json(outgoing_think)
                    logger.info("WSS OUT: %s", json.dumps(outgoing_think))

                    # Streaming response in small chunks similar to old agent (skip empty first chunk)
                    text = (await agent.process_message(msg_text)).text
                    words = text.split(" ")
                    if len(words) > 3:
                        for i in range(3, len(words), 3):
                            await ws.send_json({
                                "message": " ".join(words[:i]),
                                "data": {},
                                "type": "stream",
                            })
                            await asyncio.sleep(0.1)

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


