# session_manager.py

import json
import logging
import os

import redis

logger = logging.getLogger(__name__)

CART_TTL = int(os.getenv("CART_TTL_SECONDS", 1800))

class MockRedis:
    def __init__(self):
        self.store = {}

    def get(self, key: str) -> str | None:
        return self.store.get(key)

    def setex(self, key: str, time_val: int, value: str) -> None:
        self.store[key] = value

    def delete(self, key: str) -> None:
        if key in self.store:
            del self.store[key]

_redis_client: redis.Redis | MockRedis | None = None
_use_mock = False


def get_redis() -> redis.Redis | MockRedis:
    global _redis_client, _use_mock
    if _use_mock:
        return _redis_client

    if _redis_client is None:
        try:
            client = redis.Redis(
                host=os.getenv("REDIS_HOST", "127.0.0.1"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                password=os.getenv("REDIS_PASSWORD", None),
                decode_responses=True,
                socket_connect_timeout=1,
            )
            client.ping()
            _redis_client = client
            logger.info("Successfully connected to Redis server.")
        except Exception:
            logger.warning("Local Redis connection failed. Falling back to in-memory MockRedis.")
            _use_mock = True
            _redis_client = MockRedis()

    return _redis_client


def _cart_key(session_id: str) -> str:
    return f"cart:{session_id}"


def get_or_create_cart(session_id: str) -> dict:
    r = get_redis()
    data = r.get(_cart_key(session_id))
    return json.loads(data) if data else {}


def save_cart(session_id: str, cart: dict) -> None:
    r = get_redis()
    r.setex(_cart_key(session_id), CART_TTL, json.dumps(cart))


def clear_cart(session_id: str) -> None:
    get_redis().delete(_cart_key(session_id))