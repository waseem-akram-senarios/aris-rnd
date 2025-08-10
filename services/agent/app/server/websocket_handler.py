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

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        payload = json.loads(msg.data)
                    except json.JSONDecodeError:
                        await ws.send_json({"type": "error", "message": "invalid_json"})
                        continue

                # Optional document handling: { doc_bucket, doc_key }
                if payload.get("doc_bucket") and payload.get("doc_key"):
                    try:
                        doc_resp = await agent.process_document(payload["doc_bucket"], payload["doc_key"])  # type: ignore[attr-defined]
                        await ws.send_json({"type": "doc", "data": doc_resp})
                    except Exception as exc:
                        await ws.send_json({"type": "error", "message": f"doc_processing_failed: {exc}"})

                # Accept both {"message": ...} and old format {"action":"agent", "question": ...};
                # pass model_id through memory (simple approach for now)
                msg_text = payload.get("message")
                if msg_text is None and payload.get("action") == "agent":
                    msg_text = payload.get("question", "")
                if msg_text is None:
                    msg_text = ""

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

                    await ws.send_json({
                    "message": text,
                    "data": {},
                    "type": "message",
                    "action": "close",
                    })
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


