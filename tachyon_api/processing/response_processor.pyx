# cython: language_level=3
"""Cython-compiled response processor."""

import msgspec
from starlette.responses import Response

from ..background import BackgroundTasks
from ..models import Struct
from ..responses import TachyonJSONResponse, TachyonBytesResponse, response_validation_error_response


cdef class ResponseProcessor:

    @staticmethod
    async def process_response(
        object payload,
        object response_model,
        object background_tasks,
    ):
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
            return TachyonBytesResponse(msgspec.json.encode(payload))

        if isinstance(payload, dict):
            for key, value in payload.items():
                if isinstance(value, Struct):
                    payload[key] = msgspec.to_builtins(value)

        return TachyonJSONResponse(payload)

    @staticmethod
    async def call_endpoint(compiled, dict kwargs):
        if compiled.is_async:
            return await compiled.func(**kwargs)
        return compiled.func(**kwargs)
