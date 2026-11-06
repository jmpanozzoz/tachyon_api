"""Bounded in-process metrics and logs without URLs, queries or identities."""
import json
import logging
import re
from time import perf_counter
from uuid import uuid4

logger = logging.getLogger("reference.http")
BUCKETS = (.005, .01, .025, .05, .1, .25, .5, 1, 5)


class Metrics:
    def __init__(self):
        self.requests, self.inflight, self.errors = 0, 0, 0
        self.buckets = [0] * (len(BUCKETS) + 1)


class ObservabilityMiddleware:
    def __init__(self, app, metrics):
        self.app, self.metrics = app, metrics

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        incoming = dict(scope.get("headers", [])).get(b"x-correlation-id", b"")
        correlation = incoming.decode("ascii", "ignore")
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", correlation):
            correlation = uuid4().hex
        scope.setdefault("state", {})["correlation_id"] = correlation
        status, started = 500, perf_counter()
        self.metrics.inflight += 1
        async def traced(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                message = {**message, "headers": [
                    (k, v) for k, v in message.get("headers", []) if k.lower() != b"x-correlation-id"
                ] + [(b"x-correlation-id", correlation.encode())]}
            await send(message)
        try:
            await self.app(scope, receive, traced)
        except BaseException:
            self.metrics.errors += 1
            raise
        finally:
            duration = perf_counter() - started
            self.metrics.requests += 1
            self.metrics.inflight -= 1
            self.metrics.buckets[next((i for i, bound in enumerate(BUCKETS) if duration <= bound), len(BUCKETS))] += 1
            logger.info(json.dumps({"event": "http_request", "status": status,
                                   "duration_ms": round(duration * 1000, 3), "correlation_id": correlation}))
