"""
Admin WebSocket — showcases v1.2.0 WebSocket DI + typed path params.

What this demonstrates
----------------------

1. **Typed path params in WebSockets**: `room_id: uuid.UUID` — Tachyon parses
   the URL segment and rejects malformed UUIDs by closing the connection with
   code 1008 (policy violation) before the handler runs.

2. **`@injectable` class deps in WebSocket handlers**: `AdminBroadcaster` is
   resolved by type, singleton-scoped, shared across all admin WS connections.

3. **`Depends(callable)` factory in WebSockets**: `get_optional_user` is
   invoked once per connection during the handler setup (not per message).

Before v1.2.0, WebSocket handlers were limited to path-string + websocket.
The same routing infrastructure now resolves DI for class + callable deps.
"""

import uuid
from typing import Dict, List

from tachyon_api import Router, Depends, injectable

from ...shared.dependencies import get_optional_user


@injectable
class AdminBroadcaster:
    """Singleton service for broadcasting messages to admin WS rooms."""

    def __init__(self) -> None:
        self._rooms: Dict[str, List] = {}

    async def join(self, websocket, room_key: str) -> None:
        await websocket.accept()
        self._rooms.setdefault(room_key, []).append(websocket)

    def leave(self, websocket, room_key: str) -> None:
        room = self._rooms.get(room_key, [])
        if websocket in room:
            room.remove(websocket)
        if not room and room_key in self._rooms:
            del self._rooms[room_key]

    async def broadcast(self, room_key: str, message: dict) -> None:
        for ws in self._rooms.get(room_key, []):
            try:
                await ws.send_json(message)
            except Exception:
                pass

    def count(self, room_key: str) -> int:
        return len(self._rooms.get(room_key, []))


router = Router(prefix="/admin", tags=["Admin"])


@router.websocket("/ws/rooms/{room_id}")
async def admin_room_stream(
    websocket,
    room_id: uuid.UUID,                          # typed path param — auto-converted
    broadcaster: AdminBroadcaster = Depends(),   # @injectable singleton
    admin: dict = Depends(get_optional_user),    # callable dep (per-connection)
):
    """
    Real-time admin stream for a specific room.

    Connection URL: `ws://host/admin/ws/rooms/{room_id}`
    where `{room_id}` MUST be a valid UUID4. Invalid UUIDs cause the connection
    to close with code 1008 BEFORE this handler runs — try connecting to
    `/admin/ws/rooms/not-a-uuid` to see it in action.

    Messages from the client:
      - `{"type": "ping"}` → server responds `{"type": "pong"}`
      - `{"type": "broadcast", "payload": ...}` → forwarded to all admins in the room
    """
    room_key = str(room_id)
    await broadcaster.join(websocket, room_key)

    try:
        await websocket.send_json({
            "type": "admin_connected",
            "room_id": room_key,
            "admin": admin["email"] if admin else "anonymous",
            "active_connections": broadcaster.count(room_key),
        })

        while True:
            data = await websocket.receive_json()
            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            elif data.get("type") == "broadcast":
                await broadcaster.broadcast(
                    room_key,
                    {"type": "admin_message", "payload": data.get("payload")},
                )

    except Exception:
        pass
    finally:
        broadcaster.leave(websocket, room_key)
