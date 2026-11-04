"""Compatibility facade for running Tachyon with standard Uvicorn ASGI handling.

The experimental direct transport writer is retired. Existing protocol imports
resolve to Uvicorn's h11 implementation; responses always pass through ASGI send.
"""
from __future__ import annotations

from typing import Any


def tachyon_direct_write(cycle: Any, response: Any) -> bool:
    """Compatibility hook: tell legacy callers to use normal ASGI response handling."""
    return False


def __getattr__(name: str) -> Any:
    if name == "TachyonHTTPProtocol":
        from uvicorn.protocols.http.h11_impl import H11Protocol
        return H11Protocol
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def run(app: Any, **kwargs: Any) -> None:
    """Run an application with the caller's standard Uvicorn configuration."""
    import uvicorn
    uvicorn.run(app, **kwargs)
