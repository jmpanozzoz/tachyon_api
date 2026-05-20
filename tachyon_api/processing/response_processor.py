"""Endpoint response processing: validation, serialization, background tasks."""

from __future__ import annotations

import msgspec
from typing import Any, Optional, Type

from starlette.responses import Response  # kept for isinstance check on user-returned responses

from ..background import BackgroundTasks
from ..models import Struct
from ..responses import TachyonJSONResponse, TachyonBytesResponse, response_validation_error_response
from .compiler import CompiledEndpoint


class ResponseProcessor:
    @staticmethod
    async def process_response(
        payload: Any,
        response_model: Optional[Type[Struct]],
        background_tasks: Optional[BackgroundTasks],
    ) -> Response:
        if background_tasks is not None:
            await background_tasks.run_tasks()

        if isinstance(payload, Response):
            return payload

        if response_model is not None:
            try:
                payload = msgspec.convert(payload, response_model)
            except Exception as e:
                return response_validation_error_response(str(e))

        # Fast path: Struct → msgspec.json.encode (pure C) + minimal response wrapper
        if isinstance(payload, Struct):
            return TachyonBytesResponse(msgspec.json.encode(payload))

        if isinstance(payload, dict):
            for key, value in payload.items():
                if isinstance(value, Struct):
                    payload[key] = msgspec.to_builtins(value)

        return TachyonJSONResponse(payload)

    @staticmethod
    async def call_endpoint(compiled: CompiledEndpoint, kwargs: dict) -> Any:
        """Invoke endpoint using pre-computed is_async flag — no runtime check."""
        if compiled.is_async:
            return await compiled.func(**kwargs)
        return compiled.func(**kwargs)
