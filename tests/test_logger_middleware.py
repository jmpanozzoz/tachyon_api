import logging
import pytest
from tachyon_api import Tachyon
from tests.helpers import create_client
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

    async with create_client(app) as client:
        response = await client.get(
            "/log-test", headers={"X-Test": "1", "Authorization": "secret"}
        )

    assert response.status_code == 200

    # Validate that start and end logs were produced
    assert any(line.startswith("--> GET /log-test") for line in logs)
    assert any(line.startswith("<-- GET /log-test 200") for line in logs)

    # Headers should be logged and authorization header redacted
    headers_lines = [line for line in logs if "req headers:" in line]
    assert headers_lines, "Expected request headers to be logged"
    assert "authorization" in headers_lines[-1]
    assert "<redacted>" in headers_lines[-1]


@pytest.mark.asyncio
async def test_logger_middleware_with_body_logging():
    from tachyon_api import Struct, Body

    app = Tachyon()
    app.add_middleware(LoggerMiddleware, log_request_body=True)

    class Payload(Struct):
        msg: str

    @app.post("/data")
    def ep(data: Payload = Body()):
        return {"got": data.msg}

    async with create_client(app) as client:
        r = await client.post("/data", json={"msg": "hello"})

    assert r.status_code == 200
