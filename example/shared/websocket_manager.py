"""Short-lived single-use tickets; PostgreSQL identity and Redis cross-worker feed."""
import asyncio
from datetime import timedelta
import hashlib
import json
import secrets

import anyio

from redis.exceptions import RedisError
from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError
from starlette.websockets import WebSocketDisconnect

from .dependencies import require_owner
from .exceptions import KYCException
from .models import Customer, User, WebSocketTicket, now


async def issue_ticket(session, customer_id, user):
    require_owner(await session.get(Customer, customer_id), user)
    ticket = secrets.token_urlsafe(32)
    session.add(WebSocketTicket(digest=hashlib.sha256(ticket.encode()).hexdigest(),
                               user_id=user["user_id"], customer_id=customer_id,
                               expires_at=now() + timedelta(seconds=30)))
    await session.commit()
    return {"ticket": ticket, "expires_in": 30}


async def notifications(websocket, customer_id):
    state = websocket.app.state
    if websocket.headers.get("origin") not in state.settings.allowed_origins:
        await websocket.close(code=1008)
        return
    ticket = websocket.query_params.get("ticket", "")
    if not 20 <= len(ticket) <= 128:
        await websocket.close(code=1008)
        return
    async with state.sessions() as session:
        user_id = await session.scalar(delete(WebSocketTicket).where(
            WebSocketTicket.digest == hashlib.sha256(ticket.encode()).hexdigest(),
            WebSocketTicket.customer_id == customer_id,
            WebSocketTicket.expires_at > now(),
        ).returning(WebSocketTicket.user_id))
        user = await session.get(User, user_id) if user_id else None
        if not user or not user.active:
            await websocket.close(code=1008)
            return
        try:
            require_owner(await session.get(Customer, customer_id), {"user_id": user.user_id, "role": user.role})
        except KYCException:
            await websocket.close(code=1008)
            return
        await session.commit()
    tasks = []
    channel = state.redis.pubsub()
    try:
        await channel.subscribe(f"reference:notifications:{customer_id}")
        # Consume subscribe acknowledgement before telling the client it is ready.
        await channel.get_message(timeout=.5)
        await websocket.accept()
        await websocket.send_json({"type": "connected", "customer_id": customer_id,
                                   "reconcile": f"/customers/{customer_id}"})
        async def input_messages():
            while True:
                raw = await websocket.receive_text()
                if len(raw) > 4096:
                    await websocket.close(code=1009)
                    return
                try:
                    data = json.loads(raw)
                except ValueError:
                    await websocket.close(code=1003)
                    return
                if data != {"type": "ping"}:
                    await websocket.close(code=1008)
                    return
                await websocket.send_json({"type": "pong"})
        async def events():
            loop = asyncio.get_running_loop()
            deadline = loop.time() + state.settings.websocket_session_seconds
            next_check = 0
            while True:
                if loop.time() >= deadline:
                    await websocket.close(code=1000)
                    return
                if loop.time() >= next_check:
                    async with state.sessions() as session:
                        current = await session.get(User, user_id)
                        customer = await session.get(Customer, customer_id)
                        if current is None or not current.active or customer is None or (current.role != "admin" and customer.user_id != current.user_id):
                            await websocket.close(code=1008)
                            return
                    next_check = loop.time() + state.settings.websocket_recheck_seconds
                message = await channel.get_message(ignore_subscribe_messages=True, timeout=.2)
                if message:
                    await websocket.send_json(json.loads(message["data"]))
                await asyncio.sleep(.01)
        tasks = [asyncio.create_task(input_messages()), asyncio.create_task(events())]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    except WebSocketDisconnect:
        pass
    except (RedisError, SQLAlchemyError):
        await websocket.close(code=1013)
    finally:
        with anyio.move_on_after(2, shield=True):
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            await channel.aclose()
