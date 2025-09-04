"""
Tachyon API Example - Middlewares

This module contains middleware examples for the Tachyon API application.
Middlewares can intercept requests and responses to add functionality like:
- Logging
- Timing
- Authentication
- CORS handling
- Request/response modification
- And more
"""

import time
import logging
from datetime import datetime

# Configure basic logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("tachyon.middleware")


def setup_middlewares(app):
    """
    Setup all middlewares for the application using the decorator pattern.

    Args:
        app: The Tachyon application instance
    """

    @app.middleware()
    async def response_headers_middleware(scope, receive, send, app):
        """
        A middleware that adds custom headers to all responses.

        This demonstrates how to modify responses in a middleware.
        """
        if scope["type"] != "http":
            return await app(scope, receive, send)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                # Add custom headers to every response
                headers = list(message.get("headers", []))
                headers.append((b"X-Powered-By", b"Tachyon API"))
                headers.append((b"X-Response-Time", str(time.time()).encode()))
                message["headers"] = headers

            await send(message)

        await app(scope, receive, send_wrapper)

    @app.middleware()
    async def request_logger_middleware(scope, receive, send, app):
        """
        A middleware that logs information about each request.

        This middleware captures:
        - Request method and path
        - Timestamp when request was received
        - Time taken to process the request
        - Response status code
        """
        if scope["type"] != "http":
            # Pass through non-HTTP requests (like WebSocket)
            return await app(scope, receive, send)

        # Extract request info
        method = scope["method"]
        path = scope["path"]
        request_id = f"{time.time():.0f}"

        # Log the incoming request
        logger.info(
            f"[{request_id}] Request {method} {path} started at {datetime.now().isoformat()}"
        )
        start_time = time.time()

        # Create a wrapper for the send function to intercept the response
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                # Log response info when the response headers are sent
                status = message["status"]
                duration = time.time() - start_time
                logger.info(f"[{request_id}] Response: {status} - Took {duration:.4f}s")

            await send(message)

        # Process the request with the modified send function
        await app(scope, receive, send_wrapper)

    # Return the middleware functions for reference if needed
    return {
        "response_headers_middleware": response_headers_middleware,
        "request_logger_middleware": request_logger_middleware,
    }
