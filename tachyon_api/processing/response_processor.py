"""Endpoint response processing: validation, serialization, background tasks."""

import asyncio
import msgspec
from typing import Any, Optional, Type

from starlette.responses import Response

from ..background import BackgroundTasks
from ..models import Struct
from ..responses import TachyonJSONResponse, response_validation_error_response


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

        if isinstance(payload, Struct):
            payload = msgspec.to_builtins(payload)
        elif isinstance(payload, dict):
            for key, value in payload.items():
                if isinstance(value, Struct):
                    payload[key] = msgspec.to_builtins(value)

        return TachyonJSONResponse(payload)

    @staticmethod
    async def call_endpoint(endpoint_func, kwargs_to_inject: dict) -> Any:
        if asyncio.iscoroutinefunction(endpoint_func):
            return await endpoint_func(**kwargs_to_inject)
        else:
            return endpoint_func(**kwargs_to_inject)

