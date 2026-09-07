"""Web package for Bible Engine.

Zero-dependency implementation (Python 3 standard library only per ADR-003).
Provides local HTTP server, REST API routing, and static web asset serving.
"""

from web.server import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_STATIC_DIR,
    BibleRequestHandler,
    BibleWebServer,
    create_server,
)

__all__ = [
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "DEFAULT_STATIC_DIR",
    "BibleRequestHandler",
    "BibleWebServer",
    "create_server",
]
