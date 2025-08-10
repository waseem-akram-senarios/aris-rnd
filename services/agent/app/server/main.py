import asyncio
import logging
import os
import ssl
from pathlib import Path
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

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "443"))

    # Optional TLS similar to old agent
    cert_path = Path(os.environ.get("TLS_CERT_PATH", "/certs/server.crt"))
    key_path = Path(os.environ.get("TLS_KEY_PATH", "/certs/server.key"))
    ssl_context = None
    if cert_path.exists() and key_path.exists():
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(str(cert_path), str(key_path))

    # Use explicit runner/site to ensure binding to desired host
    runner = web.AppRunner(app)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(runner.setup())
    site = web.TCPSite(runner, host, port, ssl_context=ssl_context)
    loop.run_until_complete(site.start())
    print(f"Server running on {'https' if ssl_context else 'http'}://{host}:{port}")
    loop.run_forever()


if __name__ == "__main__":
    # uvloop is optional
    try:
        import uvloop  # type: ignore

        uvloop.install()
    except Exception:  # pragma: no cover - optional dependency
        pass

    main()


