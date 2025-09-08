"""
Response Processing System for Tachyon API

This module handles the processing and serialization of endpoint responses,
including validation against response models, Struct conversion, and final JSON serialization.
"""

import asyncio
from typing import Any, Callable, Dict, Union
from starlette.responses import Response

import msgspec

from ..schemas.models import Struct
from ..schemas.responses import (
    TachyonJSONResponse,
    response_validation_error_response,
    internal_server_error_response,
)


class ResponseProcessor:
    """
    Handles processing and serialization of endpoint responses.

    This class manages the complete response pipeline:
    - Calling endpoint functions (sync/async)
    - Response model validation and conversion
    - Struct to dict conversion
    - Final JSON serialization
    """

    @staticmethod
    async def process_response(
        endpoint_func: Callable,
        kwargs_to_inject: Dict[str, Any],
        response_model: Any = None,
    ) -> Union[Response, TachyonJSONResponse]:
        """
        Process the complete response pipeline for an endpoint.

        Args:
            endpoint_func: The endpoint function to call
            kwargs_to_inject: Arguments to inject into the endpoint function
            response_model: Optional response model for validation

        Returns:
            Processed response ready for client
        """
        try:
            # Call the endpoint function
            payload = await ResponseProcessor._call_endpoint_function(
                endpoint_func, kwargs_to_inject
            )

            # If the endpoint already returned a Response object, return it directly
            if isinstance(payload, Response):
                return payload

            # Validate/convert response against response_model if provided
            if response_model is not None:
                validation_result = ResponseProcessor._validate_response_model(
                    payload, response_model
                )
                if isinstance(validation_result, TachyonJSONResponse):
                    return validation_result  # Error response
                payload = validation_result

            # Convert Struct objects to dictionaries for JSON serialization
            payload = ResponseProcessor._convert_structs_to_dicts(payload)

            return TachyonJSONResponse(payload)

        except Exception:
            # Fallback: prevent unhandled exceptions from leaking to the client
            return internal_server_error_response()

    @staticmethod
    async def _call_endpoint_function(
        endpoint_func: Callable, kwargs_to_inject: Dict[str, Any]
    ) -> Any:
        """
        Call the endpoint function with injected parameters.

        Handles both sync and async endpoint functions.

        Args:
            endpoint_func: The endpoint function to call
            kwargs_to_inject: Arguments to inject

        Returns:
            Result of calling the endpoint function
        """
        if asyncio.iscoroutinefunction(endpoint_func):
            payload = await endpoint_func(**kwargs_to_inject)
        else:
            payload = endpoint_func(**kwargs_to_inject)
        return payload

    @staticmethod
    def _validate_response_model(
        payload: Any, response_model: Any
    ) -> Union[Any, TachyonJSONResponse]:
        """
        Validate and convert response against the response model.

        Args:
            payload: The response payload to validate
            response_model: The expected response model

        Returns:
            Validated and converted payload, or error response on validation failure
        """
        try:
            return msgspec.convert(payload, response_model)
        except Exception as e:
            return response_validation_error_response(str(e))

    @staticmethod
    def _convert_structs_to_dicts(payload: Any) -> Any:
        """
        Convert Struct objects to dictionaries for JSON serialization.

        Handles both single Struct objects and dictionaries containing Struct values.

        Args:
            payload: The payload that may contain Struct objects

        Returns:
            Payload with Struct objects converted to dictionaries
        """
        if isinstance(payload, Struct):
            return msgspec.to_builtins(payload)
        elif isinstance(payload, dict):
            # Convert any Struct values in the dictionary
            converted_payload = {}
            for key, value in payload.items():
                if isinstance(value, Struct):
                    converted_payload[key] = msgspec.to_builtins(value)
                else:
                    converted_payload[key] = value
            return converted_payload
        else:
            return payload
