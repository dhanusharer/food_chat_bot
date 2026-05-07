# db_helper.py

import logging
import os

import mysql.connector
from mysql.connector import pooling
from thefuzz import process

logger = logging.getLogger(__name__)

_pool: pooling.MySQLConnectionPool | None = None


def get_pool() -> pooling.MySQLConnectionPool:
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(
            pool_name="foodbot_pool",
            pool_size=5,
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", 3306)),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", "root"),
            database=os.getenv("DB_NAME", "chatbot_db"),
        )
    return _pool


def get_connection() -> mysql.connector.MySQLConnection:
    return get_pool().get_connection()


def create_new_order(cursor) -> int:
    cursor.execute("INSERT INTO orders (status) VALUES ('pending')")
    return cursor.lastrowid


def get_all_food_items(cursor) -> list[dict]:
    cursor.execute("SELECT id, name FROM food_items")
    return cursor.fetchall()


def get_food_item_id_fuzzy(cursor, item_name: str) -> int | None:
    threshold = int(os.getenv("FUZZY_MATCH_THRESHOLD", 70))
    all_items = get_all_food_items(cursor)

    if not all_items:
        return None

    name_map = {row["name"].lower(): row["id"] for row in all_items}
    match, score = process.extractOne(item_name.lower(), name_map.keys())

    if score < threshold:
        logger.warning("No fuzzy match for '%s' (best: '%s' @ %d)", item_name, match, score)
        return None

    logger.info("Fuzzy matched '%s' → '%s' (score: %d)", item_name, match, score)
    return name_map[match]


def insert_order_item(cursor, order_id: int, food_item_id: int, quantity: int) -> None:
    cursor.execute("SELECT price FROM food_items WHERE id = %s", (food_item_id,))
    row = cursor.fetchone()
    if not row:
        raise ValueError(f"food_item_id {food_item_id} not found")

    total_price = row["price"] * quantity
    cursor.execute(
        "INSERT INTO order_items (order_id, item_id, quantity, total_price) VALUES (%s, %s, %s, %s)",
        (order_id, food_item_id, quantity, total_price),
    )


def get_order_summary(cursor, order_id: int) -> dict | None:
    cursor.execute("SELECT status FROM orders WHERE id = %s", (order_id,))
    order = cursor.fetchone()
    if not order:
        return None

    cursor.execute(
        """
        SELECT fi.name, oi.quantity, oi.total_price
        FROM order_items oi
        JOIN food_items fi ON oi.item_id = fi.id
        WHERE oi.order_id = %s
        """,
        (order_id,),
    )
    items = cursor.fetchall()
    return {"status": order["status"], "items": items}
