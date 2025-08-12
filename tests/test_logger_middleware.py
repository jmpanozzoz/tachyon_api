import logging
import pytest
from httpx import AsyncClient, ASGITransport

from tachyon_api import Tachyon
from tachyon_api.middlewares import LoggerMiddleware


class ListHandler(logging.Handler):
    def __init__(self, records):
        super().__init__()
        self.records = records

    def emit(self, record):
        self.records.append(self.format(record))


@pytest.mark.asyncio
async def test_logger_middleware_basic_logging():
    app = Tachyon()

    logs = []
    logger = logging.getLogger("test.logger")
    logger.setLevel(logging.INFO)
    handler = ListHandler(logs)
    formatter = logging.Formatter("%(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Add logger middleware
    app.add_middleware(
        LoggerMiddleware,
        logger=logger,
        include_headers=True,
        log_request_body=False,
        redact_headers=["authorization"],
    )

    @app.get("/log-test")
    def endpoint():
        return {"ok": True}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/log-test", headers={"X-Test": "1", "Authorization": "secret"})

    assert response.status_code == 200

    # Validate that start and end logs were produced
    assert any(line.startswith("--> GET /log-test") for line in logs)
    assert any(line.startswith("<-- GET /log-test 200") for line in logs)

    # Headers should be logged and authorization header redacted
    headers_lines = [l for l in logs if "req headers:" in l]
    assert headers_lines, "Expected request headers to be logged"
    assert "authorization" in headers_lines[-1]
    assert "<redacted>" in headers_lines[-1]

