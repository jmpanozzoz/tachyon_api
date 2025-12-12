"""
Tests for Background Tasks (TDD).
Release 0.6.5 - Background Tasks
"""

import pytest
from httpx import AsyncClient, ASGITransport


# =============================================================================
# BackgroundTasks Tests
# =============================================================================


@pytest.mark.asyncio
async def test_background_task_basic():
    """BackgroundTasks should run tasks after response is sent."""
    from tachyon_api import Tachyon
    from tachyon_api.background import BackgroundTasks

    app = Tachyon()
    results = []

    def write_log(message: str):
        results.append(message)

    @app.get("/send-notification")
    def send_notification(background_tasks: BackgroundTasks):
        background_tasks.add_task(write_log, "notification sent")
        return {"message": "Notification scheduled"}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/send-notification")
        assert response.status_code == 200
        assert response.json() == {"message": "Notification scheduled"}
        # Background task should have run
        assert results == ["notification sent"]


@pytest.mark.asyncio
async def test_background_task_async():
    """BackgroundTasks should support async tasks."""
    from tachyon_api import Tachyon
    from tachyon_api.background import BackgroundTasks
    import asyncio

    app = Tachyon()
    results = []

    async def async_write(message: str):
        await asyncio.sleep(0.01)
        results.append(message)

    @app.get("/async-task")
    def async_task(background_tasks: BackgroundTasks):
        background_tasks.add_task(async_write, "async done")
        return {"status": "ok"}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/async-task")
        assert response.status_code == 200
        assert results == ["async done"]


@pytest.mark.asyncio
async def test_background_task_multiple():
    """Multiple background tasks should all run."""
    from tachyon_api import Tachyon
    from tachyon_api.background import BackgroundTasks

    app = Tachyon()
    results = []

    def task1():
        results.append("task1")

    def task2():
        results.append("task2")

    def task3():
        results.append("task3")

    @app.get("/multi")
    def multi_task(background_tasks: BackgroundTasks):
        background_tasks.add_task(task1)
        background_tasks.add_task(task2)
        background_tasks.add_task(task3)
        return {"tasks": 3}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/multi")
        assert response.status_code == 200
        assert len(results) == 3
        assert "task1" in results
        assert "task2" in results
        assert "task3" in results


@pytest.mark.asyncio
async def test_background_task_with_kwargs():
    """BackgroundTasks should support keyword arguments."""
    from tachyon_api import Tachyon
    from tachyon_api.background import BackgroundTasks

    app = Tachyon()
    results = []

    def send_email(to: str, subject: str, body: str):
        results.append({"to": to, "subject": subject, "body": body})

    @app.get("/email")
    def email_task(background_tasks: BackgroundTasks):
        background_tasks.add_task(
            send_email, to="user@example.com", subject="Hello", body="World"
        )
        return {"sent": True}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/email")
        assert response.status_code == 200
        assert len(results) == 1
        assert results[0]["to"] == "user@example.com"
        assert results[0]["subject"] == "Hello"


@pytest.mark.asyncio
async def test_background_task_with_other_params():
    """BackgroundTasks should work alongside other parameters."""
    from tachyon_api import Tachyon, Query
    from tachyon_api.background import BackgroundTasks

    app = Tachyon()
    results = []

    def log_action(action: str, user: str):
        results.append(f"{user}: {action}")

    @app.get("/action")
    def action_endpoint(
        action: str = Query(...),
        user: str = Query("anonymous"),
        background_tasks: BackgroundTasks = None,
    ):
        if background_tasks:
            background_tasks.add_task(log_action, action, user)
        return {"action": action, "user": user}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/action?action=login&user=john")
        assert response.status_code == 200
        assert response.json() == {"action": "login", "user": "john"}
        assert results == ["john: login"]


@pytest.mark.asyncio
async def test_background_task_error_handling():
    """Background task errors should not affect response."""
    from tachyon_api import Tachyon
    from tachyon_api.background import BackgroundTasks

    app = Tachyon()
    results = []

    def failing_task():
        raise ValueError("Task failed!")

    def success_task():
        results.append("success")

    @app.get("/with-error")
    def with_error(background_tasks: BackgroundTasks):
        background_tasks.add_task(failing_task)
        background_tasks.add_task(success_task)
        return {"status": "ok"}

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/with-error")
        # Response should still be 200
        assert response.status_code == 200
        # Success task should have run despite failing task
        assert "success" in results
