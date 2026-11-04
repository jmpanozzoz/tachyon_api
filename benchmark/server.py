"""Explicit server selection for local ASGI measurements and contracts."""
import importlib.util
import sys


def server_command(server, target, port, http="h11", lifespan=False):
    common = ["--host", "127.0.0.1", "--port", str(port), "--workers", "1", "--loop", "asyncio"]
    if server == "granian":
        if http != "h11":
            raise ValueError("--http selects the Uvicorn parser; omit it for Granian")
        if importlib.util.find_spec("granian") is None:
            raise RuntimeError('Install the optional server with pip install "tachyon-api[granian]"')
        return [sys.executable, "-m", "granian", "--interface", "asgi" if lifespan else "asginl",
                *common, "--runtime-threads", "1", "--http", "1", "--log-level", "warning", target]
    if server != "uvicorn":
        raise ValueError(f"Unknown server: {server}")
    return [sys.executable, "-m", "uvicorn", target, *common, "--http", http,
            "--lifespan", "on" if lifespan else "off", "--no-access-log", "--log-level", "warning"]
