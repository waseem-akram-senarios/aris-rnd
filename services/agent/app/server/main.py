import asyncio
import logging
import os
from aiohttp import web

from .websocket_handler import WebSocketHandler
from ..config.settings import load_settings


def create_app() -> web.Application:
    settings = load_settings()

    app = web.Application()
    handler = WebSocketHandler(settings=settings)

    async def healthcheck(_request: web.Request) -> web.Response:
        return web.json_response({"status": "ok"})

    app.router.add_get("/health", healthcheck)
    app.router.add_get("/ws", handler.handle_connection)

    return app


def _configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def main() -> None:
    _configure_logging()
    app = create_app()
    web.run_app(app, host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", "8080")))


if __name__ == "__main__":
    # uvloop is optional
    try:
        import uvloop  # type: ignore

        uvloop.install()
    except Exception:  # pragma: no cover - optional dependency
        pass

    main()


