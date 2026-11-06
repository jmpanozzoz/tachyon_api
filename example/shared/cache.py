"""Bounded Redis operations; cache failure never changes authorization."""
import json
import logging

from redis.exceptions import RedisError

logger = logging.getLogger("reference.cache")


class Cache:
    def __init__(self, redis, ttl=30):
        self.redis, self.ttl = redis, ttl

    async def get(self, key):
        try:
            value = await self.redis.get(key)
            return json.loads(value) if value else None
        except (RedisError, ValueError):
            logger.warning("Cache read unavailable")
            return None

    async def set(self, key, value):
        try:
            await self.redis.set(key, json.dumps(value), ex=self.ttl)
        except RedisError:
            logger.warning("Cache write unavailable")

    async def invalidate_customer(self, customer_id, owner_id):
        await self.redis.delete(f"reference:customer:{owner_id}:{customer_id}",
                                f"reference:customer:admin:{customer_id}")
