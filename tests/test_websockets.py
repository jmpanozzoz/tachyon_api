"""
Tests for WebSocket support (TDD).
Release 0.7.0 - WebSockets
"""

from starlette.testclient import TestClient


# =============================================================================
# WebSocket Decorator Tests
# =============================================================================


class TestWebSocketDecorator:
    """Tests for @app.websocket decorator."""

    def test_websocket_basic_echo(self):
        """Should handle basic WebSocket echo."""
        from tachyon_api import Tachyon

        app = Tachyon()

        @app.websocket("/ws")
        async def websocket_endpoint(websocket):
            await websocket.accept()
            data = await websocket.receive_text()
            await websocket.send_text(f"Echo: {data}")
            await websocket.close()

        client = TestClient(app)
        with client.websocket_connect("/ws") as ws:
            ws.send_text("Hello")
            response = ws.receive_text()
            assert response == "Echo: Hello"

    def test_websocket_json_messages(self):
        """Should handle JSON messages."""
        from tachyon_api import Tachyon

        app = Tachyon()

        @app.websocket("/ws/json")
        async def json_endpoint(websocket):
            await websocket.accept()
            data = await websocket.receive_json()
            await websocket.send_json({"received": data["message"]})
            await websocket.close()

        client = TestClient(app)
        with client.websocket_connect("/ws/json") as ws:
            ws.send_json({"message": "Hello JSON"})
            response = ws.receive_json()
            assert response == {"received": "Hello JSON"}

    def test_websocket_binary_data(self):
        """Should handle binary data."""
        from tachyon_api import Tachyon

        app = Tachyon()

        @app.websocket("/ws/binary")
        async def binary_endpoint(websocket):
            await websocket.accept()
            data = await websocket.receive_bytes()
            await websocket.send_bytes(data[::-1])  # Reverse bytes
            await websocket.close()

        client = TestClient(app)
        with client.websocket_connect("/ws/binary") as ws:
            ws.send_bytes(b"Hello")
            response = ws.receive_bytes()
            assert response == b"olleH"

    def test_websocket_multiple_messages(self):
        """Should handle multiple messages in a session."""
        from tachyon_api import Tachyon

        app = Tachyon()

        @app.websocket("/ws/chat")
        async def chat_endpoint(websocket):
            await websocket.accept()
            for _ in range(3):
                data = await websocket.receive_text()
                await websocket.send_text(f"Got: {data}")
            await websocket.close()

        client = TestClient(app)
        with client.websocket_connect("/ws/chat") as ws:
            for i in range(3):
                ws.send_text(f"Message {i}")
                response = ws.receive_text()
                assert response == f"Got: Message {i}"

    def test_websocket_with_path_params(self):
        """Should support path parameters."""
        from tachyon_api import Tachyon

        app = Tachyon()

        @app.websocket("/ws/{room_id}")
        async def room_endpoint(websocket, room_id: str):
            await websocket.accept()
            await websocket.send_text(f"Welcome to room: {room_id}")
            await websocket.close()

        client = TestClient(app)
        with client.websocket_connect("/ws/lobby") as ws:
            response = ws.receive_text()
            assert response == "Welcome to room: lobby"

    def test_websocket_with_query_params(self):
        """Should support query parameters."""
        from tachyon_api import Tachyon

        app = Tachyon()

        @app.websocket("/ws/auth")
        async def auth_endpoint(websocket):
            await websocket.accept()
            # Access query params from scope
            token = websocket.query_params.get("token", "none")
            await websocket.send_text(f"Token: {token}")
            await websocket.close()

        client = TestClient(app)
        with client.websocket_connect("/ws/auth?token=abc123") as ws:
            response = ws.receive_text()
            assert response == "Token: abc123"


# =============================================================================
# WebSocket in Router Tests
# =============================================================================


class TestWebSocketRouter:
    """Tests for WebSocket routes in Router."""

    def test_websocket_in_router(self):
        """Should support WebSocket in Router."""
        from tachyon_api import Tachyon, Router

        router = Router(prefix="/api")

        @router.websocket("/ws")
        async def router_ws(websocket):
            await websocket.accept()
            await websocket.send_text("From router!")
            await websocket.close()

        app = Tachyon()
        app.include_router(router)

        client = TestClient(app)
        with client.websocket_connect("/api/ws") as ws:
            response = ws.receive_text()
            assert response == "From router!"

    def test_multiple_websocket_routes(self):
        """Should handle multiple WebSocket routes."""
        from tachyon_api import Tachyon

        app = Tachyon()

        @app.websocket("/ws/a")
        async def ws_a(websocket):
            await websocket.accept()
            await websocket.send_text("Route A")
            await websocket.close()

        @app.websocket("/ws/b")
        async def ws_b(websocket):
            await websocket.accept()
            await websocket.send_text("Route B")
            await websocket.close()

        client = TestClient(app)

        with client.websocket_connect("/ws/a") as ws:
            assert ws.receive_text() == "Route A"

        with client.websocket_connect("/ws/b") as ws:
            assert ws.receive_text() == "Route B"


# =============================================================================
# WebSocket Error Handling Tests
# =============================================================================


class TestWebSocketErrors:
    """Tests for WebSocket error scenarios."""

    def test_websocket_disconnect_handling(self):
        """Should handle client disconnection."""
        from tachyon_api import Tachyon
        from starlette.websockets import WebSocketDisconnect

        app = Tachyon()
        disconnect_received = []

        @app.websocket("/ws/disconnect")
        async def disconnect_endpoint(websocket):
            await websocket.accept()
            try:
                while True:
                    data = await websocket.receive_text()
                    await websocket.send_text(f"Echo: {data}")
            except WebSocketDisconnect:
                disconnect_received.append(True)

        client = TestClient(app)
        with client.websocket_connect("/ws/disconnect") as ws:
            ws.send_text("Hello")
            ws.receive_text()
            # Client disconnects when exiting context

        assert disconnect_received == [True]
