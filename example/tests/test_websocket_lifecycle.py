"""Exercise the actual notification channel within the application's lifespan."""

from example.app import app
from example.config import settings
from example.shared.websocket_manager import manager
from tachyon_api.testing import TachyonTestClient


def test_notification_channel_and_lifespan(monkeypatch):
    events = []
    original_disconnect_all = manager.disconnect_all

    async def record_shutdown():
        events.append("shutdown")
        await original_disconnect_all()

    monkeypatch.setattr(manager, "disconnect_all", record_shutdown)
    with TachyonTestClient(app) as client:
        assert app.state.settings is settings
        assert app.state.ws_manager is manager
        assert app.state.verification_provider == "MockVerificationProvider"
        assert client.get("/health").status_code == 200
        with client.websocket_connect("/ws/notifications/customer-test") as websocket:
            connected = websocket.receive_json()
            assert connected["type"] == "connected"
            assert "customer-test" in connected["message"]
            assert manager.get_connection_count("customer-test") == 1
            websocket.send_json({"type": "ping"})
            assert websocket.receive_json() == {"type": "pong"}
            client.portal.call(
                manager.notify_verification_status,
                "customer-test", "verification-test", "approved", {"verified": True},
            )
            assert websocket.receive_json() == {
                "type": "verification_status", "verification_id": "verification-test",
                "status": "approved", "details": {"verified": True},
            }
        assert manager.get_connection_count() == 0
    assert events == ["shutdown"]
    assert manager.get_connection_count() == 0
