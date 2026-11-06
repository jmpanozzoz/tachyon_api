"""Real Redis pubsub notifications, single-use tickets and ownership."""
import json
import pytest
from starlette.websockets import WebSocketDisconnect


def test_ticket_required_and_origin_checked_before_accept(client, customer, auth_headers):
    path = "/ws/notifications/" + customer["customer_id"]
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(path, headers={"Origin": "http://localhost:3000"}):
            pass
    ticket = client.post("/customers/" + customer["customer_id"] + "/notification-ticket", headers=auth_headers).json()["ticket"]
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(path + "?ticket=" + ticket, headers={"Origin": "https://untrusted.invalid"}):
            pass
    with client.websocket_connect(path + "?ticket=" + ticket, headers={"Origin": "http://localhost:3000"}) as ws:
        assert ws.receive_json()["type"] == "connected"
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}
        client.portal.call(client.app.state.redis.publish, "reference:notifications:" + customer["customer_id"], json.dumps({"type": "test"}))
        assert ws.receive_json() == {"type": "test"}
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(path + "?ticket=" + ticket, headers={"Origin": "http://localhost:3000"}):
            pass


def test_lifespan_closes_engine(client):
    assert client.app.state.engine.pool.checkedout() == 0
    assert client.get("/health/ready").status_code == 200
    assert client.get("/health/live").json() == {"status": "alive"}


@pytest.mark.parametrize("reason", ["expired", "disabled"])
def test_expired_or_disabled_ticket_is_rejected(client, customer, auth_headers, identity, reason):
    from datetime import timedelta
    from sqlalchemy import select
    from example.shared.models import User, WebSocketTicket, now
    ticket = client.post("/customers/" + customer["customer_id"] + "/notification-ticket", headers=auth_headers).json()["ticket"]
    async def invalidate():
        async with client.app.state.sessions() as session, session.begin():
            if reason == "disabled":
                (await session.get(User, identity[0]["user_id"])).active = False
            else:
                (await session.scalar(select(WebSocketTicket))).expires_at = now() - timedelta(seconds=1)
    client.portal.call(invalidate)
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/notifications/" + customer["customer_id"] + "?ticket=" + ticket,
                                      headers={"Origin": "http://localhost:3000"}):
            pass
