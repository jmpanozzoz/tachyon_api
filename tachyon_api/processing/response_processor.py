"""
Response processing for Tachyon applications.

Handles:
- Response model validation
- Struct serialization
- Background task execution
- Response type detection
"""

import asyncio
import msgspec
from typing import Any, Optional

from starlette.responses import Response

from ..models import Struct
from ..responses import TachyonJSONResponse, response_validation_error_response


class ResponseProcessor:
    """
    Processes endpoint return values into HTTP responses.
    
    This class encapsulates the logic for:
    - Running background tasks
    - Validating against response_model
    - Converting Struct to JSON
    - Creating TachyonJSONResponse
    """
    
    @staticmethod
    async def process_response(
        payload: Any,
        response_model: Optional[type],
        background_tasks: Optional[Any],
    ) -> Response:
        """
        Process the endpoint return value into an HTTP response.
        
        Args:
            payload: The value returned by the endpoint
            response_model: Optional Struct class for validation
            background_tasks: Optional BackgroundTasks instance to execute
        
        Returns:
            A Starlette Response object
        """
        # Run background tasks if any were registered
        if background_tasks is not None:
            await background_tasks.run_tasks()

        # If the endpoint already returned a Response object, return it directly
        if isinstance(payload, Response):
            return payload

        # Validate/convert response against response_model if provided
        if response_model is not None:
            try:
                payload = msgspec.convert(payload, response_model)
            except Exception as e:
                return response_validation_error_response(str(e))

        # Convert Struct objects to dictionaries for JSON serialization
        if isinstance(payload, Struct):
            payload = msgspec.to_builtins(payload)
        elif isinstance(payload, dict):
            # Convert any Struct values in the dictionary
            for key, value in payload.items():
                if isinstance(value, Struct):
                    payload[key] = msgspec.to_builtins(value)

        return TachyonJSONResponse(payload)
    
    @staticmethod
    async def call_endpoint(
        endpoint_func,
        kwargs_to_inject: dict,
    ) -> Any:
        """
        Call the endpoint function with injected parameters.
        
        Args:
            endpoint_func: The endpoint function to call
            kwargs_to_inject: Dictionary of parameters to inject
        
        Returns:
            The payload returned by the endpoint
        """
        if asyncio.iscoroutinefunction(endpoint_func):
            return await endpoint_func(**kwargs_to_inject)
        else:
            return endpoint_func(**kwargs_to_inject)

