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

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True, buffered=True)

        # Resolve items FIRST before creating the order
        skipped = []
        resolved_items = []

        for item, qty in cart.items():
            food_id = get_food_item_id_fuzzy(cursor, item)

            if not food_id:
                logger.warning("Item not found in DB: %s", item)
                skipped.append(item)
                continue

            resolved_items.append((food_id, int(qty)))

        if not resolved_items:
            return _fulfillment(
                "I couldn't match anything in your cart to the menu. Please check the menu and try again."
            )

        # Only create order if we have valid items
        order_id = create_new_order(cursor)
        for food_id, qty in resolved_items:
            insert_order_item(cursor, order_id, food_id, qty)

        conn.commit()

        clear_cart(session_id)

        # Generate Razorpay payment link
        payment_result = handle_payment(order_id, session_id)
        msg = payment_result["fulfillmentText"]

        if skipped:
            msg += f"\n(Could not find: {', '.join(skipped)})"

        return _fulfillment(msg)

    except Exception:
        logger.exception("Failed to complete order for session %s", session_id)
        return _fulfillment("Something went wrong placing your order. Please try again.")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


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

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True, buffered=True)
        summary = get_order_summary(cursor, order_id)
    except Exception:
        logger.exception("Failed to fetch order %s", order_id)
        return _fulfillment("Couldn't fetch your order right now. Try again shortly.")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

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
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True, buffered=True)
        cursor.execute("SELECT name, price FROM food_items ORDER BY name")
        items = cursor.fetchall()

        if not items:
            return _fulfillment("Menu is not available right now.")

        lines = [f"• {item['name'].title()} — ₹{item['price']}" for item in items]
        return _fulfillment("🍽️ Here's our menu:\n" + "\n".join(lines) + "\n\nWhat would you like to order?")

    except Exception:
        logger.exception("Failed to fetch menu")
        return _fulfillment("Couldn't load the menu right now. Try again shortly.")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


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

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True, buffered=True)

        cursor.execute("SELECT status FROM orders WHERE id = %s", (order_id,))
        order = cursor.fetchone()

        if not order:
            return _fulfillment(f"Order #{order_id} not found.")

        if order["status"] != "pending":
            return _fulfillment(
                f"Order #{order_id} is already {order['status']} and cannot be cancelled."
            )

        cursor.execute(
            "UPDATE orders SET status = 'cancelled' WHERE id = %s", (order_id,)
        )
        conn.commit()

        logger.info("Order #%s cancelled", order_id)
        return _fulfillment(f"❌ Order #{order_id} has been cancelled successfully.")

    except Exception:
        logger.exception("Failed to cancel order %s", order_id)
        return _fulfillment("Something went wrong. Please try again.")
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ------------------------------------------
# 💳 PAYMENT LINK GENERATION
# ------------------------------------------
def handle_payment(order_id: int, session_id: str) -> dict:
    from payment_helper import create_payment_link

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True, buffered=True)

        # Get order total
        cursor.execute(
            "SELECT SUM(total_price) as total FROM order_items WHERE order_id = %s",
            (order_id,)
        )
        result = cursor.fetchone()

        if not result or not result["total"]:
            return _fulfillment(f"✅ Order #{order_id} placed! Pay at delivery.")

        total = float(result["total"])
        amount_paise = int(total * 100)  # Convert ₹ to paise

        payment_url = create_payment_link(
            order_id=order_id,
            amount_paise=amount_paise,
            description=f"FoodieBot Order #{order_id}"
        )

        return _fulfillment(
            f"✅ Order #{order_id} placed!\n"
            f"💰 Total: ₹{total:.2f}\n\n"
            f"💳 Pay here 👉 {payment_url}\n"
            f"⏰ Link expires in 15 minutes."
        )

    except Exception:
        logger.exception("Payment link generation failed for order #%s", order_id)
        return _fulfillment(
            f"✅ Order #{order_id} placed successfully! "
            f"Track it by saying 'track order {order_id}'."
        )
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
