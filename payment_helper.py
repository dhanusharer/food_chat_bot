# payment_helper.py

import hashlib
import hmac
import logging
import os

import razorpay

logger = logging.getLogger(__name__)

def get_razorpay_client() -> razorpay.Client:
    key_id = os.getenv("RAZORPAY_KEY_ID")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET")
    if not key_id or not key_secret:
        raise ValueError("Razorpay credentials not set")
    return razorpay.Client(auth=(key_id, key_secret))


def create_payment_link(order_id: int, amount_paise: int, description: str) -> str:
    """
    Creates a Razorpay payment link and returns the short URL.
    amount_paise: amount in paise (₹1 = 100 paise)
    """
    client = get_razorpay_client()

    payment_link = client.payment_link.create({
        "amount": amount_paise,
        "currency": "INR",
        "reference_id": str(order_id),
        "description": description,
        "reminder_enable": False,
        "notify": {
            "sms": False,
            "email": False
        },
        "notes": {
            "order_id": str(order_id)
        },
        "callback_url": f"{os.getenv('APP_URL', 'https://foodchatbot-production.up.railway.app')}/payment/callback",
        "callback_method": "get",
        "expire_by": int(__import__('time').time()) + 1200  # 20 min expiry
    })

    logger.info("Payment link created for order #%s: %s", order_id, payment_link["short_url"])
    return payment_link["short_url"]


def verify_payment_signature(payment_link_id: str, payment_id: str, signature: str) -> bool:
    """Verify Razorpay payment signature."""
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "")
    msg = f"{payment_link_id}|{payment_id}"
    expected = hmac.new(
        key_secret.encode(),
        msg.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
