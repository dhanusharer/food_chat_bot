# handlers.py

import logging
import os

from db_helper import (
    create_new_order,
    get_connection,
    get_food_item_id_fuzzy,
    get_order_summary,
    insert_order_item,
)
from session_manager import clear_cart, get_or_create_cart, save_cart

logger = logging.getLogger(__name__)

MAX_QTY = int(os.getenv("MAX_ITEM_QUANTITY", 20))


def _fulfillment(text: str) -> dict:
    return {"fulfillmentText": text}


# ------------------------------------------
# 🛒 ADD TO CART
# ------------------------------------------
def handle_order_add(parameters: dict, session_id: str) -> dict:
    food_items: list = parameters.get("food_items", [])
    quantities: list = parameters.get("number", [])

    if not food_items:
        return _fulfillment("What would you like to add?")

    if len(food_items) != len(quantities):
        return _fulfillment("I didn't catch the quantities. Could you repeat that?")

    cart = get_or_create_cart(session_id)
    added = []

    for item, qty in zip(food_items, quantities):
        item = item.strip().lower()
        qty = float(qty)

        if qty <= 0 or qty > MAX_QTY:
            return _fulfillment(f"Quantity for {item} must be between 1 and {MAX_QTY}.")

        cart[item] = cart.get(item, 0) + qty
        added.append(f"{int(qty)}x {item}")

    save_cart(session_id, cart)
    logger.info("Cart updated for %s: %s", session_id, cart)

    return _fulfillment(f"Added {', '.join(added)} to your cart. Anything else?")


# ------------------------------------------
# ❌ REMOVE FROM CART
# ------------------------------------------
def handle_order_remove(parameters: dict, session_id: str) -> dict:
    food_items: list = parameters.get("food_items", [])

    if not food_items:
        return _fulfillment("What would you like to remove?")

    cart = get_or_create_cart(session_id)
    removed = []
    not_found = []

    for item in food_items:
        item = item.strip().lower()
        if item in cart:
            del cart[item]
            removed.append(item)
        else:
            not_found.append(item)

    save_cart(session_id, cart)

    parts = []
    if removed:
        parts.append(f"Removed {', '.join(removed)}.")
    if not_found:
        parts.append(f"Couldn't find {', '.join(not_found)} in your cart.")

    return _fulfillment(" ".join(parts) + " Anything else?")


# ------------------------------------------
# 📋 CART SUMMARY
# ------------------------------------------
def handle_cart_summary(session_id: str) -> dict:
    cart = get_or_create_cart(session_id)

    if not cart:
        return _fulfillment("Your cart is empty.")

    lines = [f"• {int(qty)}x {item}" for item, qty in cart.items()]
    return _fulfillment("Here's your cart:\n" + "\n".join(lines) + "\n\nSay 'confirm order' to place it.")


# ------------------------------------------
# ✅ COMPLETE ORDER
# ------------------------------------------
def handle_order_complete(session_id: str) -> dict:
    cart = get_or_create_cart(session_id)

    if not cart:
        return _fulfillment("Your cart is empty. Add some items first!")

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True, buffered=True)

        order_id = create_new_order(cursor)
        skipped = []

        for item, qty in cart.items():
            food_id = get_food_item_id_fuzzy(cursor, item)

            if not food_id:
                logger.warning("Item not found in DB: %s", item)
                skipped.append(item)
                continue

            insert_order_item(cursor, order_id, food_id, int(qty))

        conn.commit()
        cursor.close()
        conn.close()

        clear_cart(session_id)

        msg = f"✅ Order #{order_id} placed successfully!"
        if skipped:
            msg += f" (Could not find: {', '.join(skipped)})"
        msg += f" Track it by saying 'track order {order_id}'."

        return _fulfillment(msg)

    except Exception:
        logger.exception("Failed to complete order for session %s", session_id)
        return _fulfillment("Something went wrong placing your order. Please try again.")


# ------------------------------------------
# 📦 TRACK ORDER
# ------------------------------------------
def handle_track_order(parameters: dict) -> dict:
    order_id = parameters.get("order_id")

    if not order_id:
        return _fulfillment("Please provide your order ID.")

    try:
        order_id = int(order_id)
    except (ValueError, TypeError):
        return _fulfillment("That doesn't look like a valid order ID.")

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True, buffered=True)
        summary = get_order_summary(cursor, order_id)
        cursor.close()
        conn.close()
    except Exception:
        logger.exception("Failed to fetch order %s", order_id)
        return _fulfillment("Couldn't fetch your order right now. Try again shortly.")

    if not summary:
        return _fulfillment(f"Order #{order_id} not found.")

    items = summary["items"]
    total = sum(i["total_price"] for i in items)
    lines = [f"• {i['quantity']}x {i['name']} — ₹{i['total_price']}" for i in items]

    return _fulfillment(
        f"Order #{order_id} is {summary['status']}.\n"
        + "\n".join(lines)
        + f"\n\nTotal: ₹{total:.2f}"
    )


# ------------------------------------------
# 🍽️ SHOW MENU
# ------------------------------------------
def handle_show_menu() -> dict:
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT name, price FROM food_items ORDER BY name")
        items = cursor.fetchall()
        cursor.close()
        conn.close()

        if not items:
            return _fulfillment("Menu is not available right now.")

        lines = [f"• {item['name'].title()} — ₹{item['price']}" for item in items]
        return _fulfillment("🍽️ Here's our menu:\n" + "\n".join(lines) + "\n\nWhat would you like to order?")

    except Exception:
        logger.exception("Failed to fetch menu")
        return _fulfillment("Couldn't load the menu right now. Try again shortly.")


# ------------------------------------------
# 🚫 CANCEL ORDER
# ------------------------------------------
def handle_cancel_order(parameters: dict) -> dict:
    order_id = parameters.get("order_id")

    if not order_id:
        return _fulfillment("Which order ID would you like to cancel?")

    try:
        order_id = int(order_id)
    except (ValueError, TypeError):
        return _fulfillment("That doesn't look like a valid order ID.")

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True, buffered=True)

        cursor.execute("SELECT status FROM orders WHERE id = %s", (order_id,))
        order = cursor.fetchone()

        if not order:
            cursor.close()
            conn.close()
            return _fulfillment(f"Order #{order_id} not found.")

        if order["status"] != "pending":
            cursor.close()
            conn.close()
            return _fulfillment(
                f"Order #{order_id} is already {order['status']} and cannot be cancelled."
            )

        cursor.execute(
            "UPDATE orders SET status = 'cancelled' WHERE id = %s", (order_id,)
        )
        conn.commit()
        cursor.close()
        conn.close()

        logger.info("Order #%s cancelled", order_id)
        return _fulfillment(f"❌ Order #{order_id} has been cancelled successfully.")

    except Exception:
        logger.exception("Failed to cancel order %s", order_id)
        return _fulfillment("Something went wrong. Please try again.")