"""Small PostgreSQL queue with leases, fencing tokens and bounded retries."""
from datetime import timedelta
import json

from sqlalchemy import and_, or_, select, delete

from ...shared.models import Customer, Event, Job, Verification, WebSocketTicket, identifier, now


async def claim(sessions, settings):
    async with sessions() as session, session.begin():
        job = await session.scalar(select(Job).where(or_(
            and_(Job.state == "pending", Job.available_at <= now()),
            and_(Job.state == "running", Job.lease_until < now()),
        )).order_by(Job.available_at).with_for_update(skip_locked=True).limit(1))
        if job is None:
            return None
        verification = await session.get(Verification, job.verification_id)
        if job.attempts >= settings.job_max_attempts or verification.expires_at < now():
            await finish(session, job, verification, "expired" if verification.expires_at < now() else "failed")
            return None
        job.state, job.lease_token = "running", identifier()
        job.lease_until = now() + timedelta(seconds=settings.job_lease_seconds)
        job.attempts += 1
        return job.verification_id, job.lease_token


async def finish(session, job, verification, status):
    verification.status = status
    verification.completed_at = now()
    job.state = "done" if status in {"verified", "rejected"} else "failed"
    job.lease_token, job.lease_until = None, None
    customer = await session.get(Customer, verification.customer_id)
    customer.kyc_status, customer.updated_at = status, now()
    session.add(Event(customer_id=customer.customer_id, payload={
        "type": "verification_status", "verification_id": verification.verification_id,
        "status": status, "details": {},
    }))


async def process(sessions, settings, claimed):
    verification_id, token = claimed
    # A real external provider would need timeouts and its own idempotency key.
    # This deterministic provider is synthetic, never real KYC decision-making.
    timed_out = settings.provider_result == "timeout"
    async with sessions() as session, session.begin():
        job = await session.scalar(select(Job).where(Job.verification_id == verification_id).with_for_update())
        if job.state != "running" or job.lease_token != token or job.lease_until < now():
            return False  # A stale worker cannot overwrite a newer claim.
        verification = await session.get(Verification, verification_id)
        if timed_out:
            if job.attempts >= settings.job_max_attempts:
                await finish(session, job, verification, "failed")
            else:
                job.state, job.lease_until, job.lease_token = "pending", None, None
                job.available_at = now() + timedelta(seconds=min(60, 2 ** job.attempts))
            return False
        result = settings.provider_result
        verification.checks = [{**c, "status": result, "checked_at": now().isoformat(),
                                "details": "Synthetic provider result"} for c in verification.checks]
        verification.risk_score = 0 if result == "passed" else 100
        await finish(session, job, verification, "verified" if result == "passed" else "rejected")
        return True


async def publish_one(sessions, cache):
    async with sessions() as session, session.begin():
        event = await session.scalar(select(Event).where(Event.published.is_(False)).order_by(
            Event.created_at).with_for_update(skip_locked=True).limit(1))
        if event is None:
            return False
        customer = await session.get(Customer, event.customer_id)
        await cache.invalidate_customer(customer.customer_id, customer.user_id)
        payload = {**event.payload, "event_id": event.event_id}
        await cache.redis.publish(f"reference:notifications:{customer.customer_id}", json.dumps(payload))
        event.published = True
        # Publication can be repeated after a crash; clients reconcile via HTTP.
        return True


async def prune(sessions):
    async with sessions() as session, session.begin():
        await session.execute(delete(WebSocketTicket).where(WebSocketTicket.expires_at < now()))
        await session.execute(delete(Event).where(Event.published.is_(True), Event.created_at < now() - timedelta(days=7)))
