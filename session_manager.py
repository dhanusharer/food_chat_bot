# session_manager.py

import json
import logging
import os

import redis

logger = logging.getLogger(__name__)

CART_TTL = int(os.getenv("CART_TTL_SECONDS", 1800))

_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", 6379)),
            decode_responses=True,
        )
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
