# cython: language_level=3
"""Endpoint invocation and response construction, without mutating user values."""

import msgspec
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response

from ..models import Struct
from ..responses._background import _BackgroundResponse
from ..responses import TachyonBytesResponse, TachyonJSONResponse, response_validation_error_response


cdef class ResponseProcessor:
    @staticmethod
    async def process_response(payload, response_model, background_tasks):
        response = ResponseProcessor._build_response(payload, response_model)
        if background_tasks:
            return _BackgroundResponse(response, background_tasks)
        return response

    @staticmethod
    def _build_response(payload, response_model):
        if isinstance(payload, Response):
            return payload
        if response_model is not None:
            try:
                # Validate the actual JSON representation, including constructed
                # Structs, nested mutations and non-finite numeric values.
                payload = msgspec.json.decode(msgspec.json.encode(payload), type=response_model)
            except (msgspec.ValidationError, TypeError, ValueError) as exc:
                return response_validation_error_response(str(exc))
            return TachyonBytesResponse(msgspec.json.encode(payload))
        if isinstance(payload, Struct):
            return TachyonBytesResponse(msgspec.json.encode(payload))
        return TachyonJSONResponse(payload)

    @staticmethod
    async def call_endpoint(compiled, args):
        if compiled.keyword_names is not None:
            kwargs = dict(zip(compiled.keyword_names, args))
            if compiled.is_async:
                return await compiled.func(**kwargs)
            return await run_in_threadpool(compiled.func, **kwargs)
        if compiled.is_async:
            return await compiled.func(*args)
        return await run_in_threadpool(compiled.func, *args)
