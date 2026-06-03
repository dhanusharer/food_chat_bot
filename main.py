# main.py

import json
import logging
import os
import re
import time
import uuid

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import service_account
from pydantic import BaseModel

from db_helper import get_connection, get_food_item_names
from handlers import (
    handle_cancel_order,
    handle_cart_summary,
    handle_order_add,
    handle_order_complete,
    handle_order_remove,
    handle_show_menu,
    handle_track_order,
)
from session_manager import get_or_create_cart

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="FoodieBot Webhook", version="1.0.0")
ORDER_HINTS = (
    "add",
    "order",
    "get",
    "give me",
    "i want",
    "i would like",
    "i need",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------
# 🔐 Dialogflow Auth
# ------------------------------------------
def get_dialogflow_token() -> str:
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if not creds_json:
        raise ValueError("GOOGLE_CREDENTIALS_JSON not set")
    creds_dict = json.loads(creds_json)
    creds = service_account.Credentials.from_service_account_info(
        creds_dict,
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    creds.refresh(GoogleRequest())
    return creds.token


# ------------------------------------------
# 💬 /chat — React frontend endpoint
# ------------------------------------------
class ChatRequest(BaseModel):
    message: str
    session_id: str = None


def _reply(text: str, session_id: str) -> JSONResponse:
    return JSONResponse({"response": text, "session_id": session_id})


def _known_food_terms() -> set[str]:
    try:
        names = get_food_item_names()
    except Exception:
        logger.exception("Could not load menu terms for local fallback")
        return set()

    terms = set()
    for name in names:
        normalized = name.lower().strip()
        if normalized:
            terms.add(normalized)
        terms.update(part for part in re.findall(r"[a-z]+", normalized) if len(part) > 2)
    return terms


def _contains_known_food(text: str) -> bool:
    return any(re.search(rf"\b{re.escape(term)}\b", text) for term in _known_food_terms())


def _is_dialogflow_fallback(intent_name: str) -> bool:
    return "fallback" in intent_name or intent_name in {
        "",
        "default fallback intent",
    }


def _parse_order_items(text: str) -> tuple[list[str], list[int]]:
    text = text.lower().strip()
    looks_like_order = any(
        re.search(rf"\b{re.escape(hint)}\b", text) for hint in ORDER_HINTS
    ) or bool(re.search(r"\b\d+\b", text))
    if not looks_like_order and not _contains_known_food(text):
        return [], []

    cleaned = re.sub(
        r"\b(i\s+want|i\s+would\s+like|i\s+need|please\s+add|add|order|get|give\s+me)\b",
        "",
        text,
    )
    parts = re.split(r"\s+(?:and|with)\s+|,", cleaned)
    food_items = []
    quantities = []
    for part in parts:
        part = part.strip().lower()
        if not part:
            continue
        # Try with quantity first: "2 burgers"
        match = re.search(r"\b(\d+)\s+([a-z][a-z\s-]*)$", part)
        if match:
            food_items.append(match.group(2).strip(" ."))
            quantities.append(int(match.group(1)))
            continue
        # Try without quantity: "naan", "ice cream" → default 1
        match2 = re.search(r"^([a-z][a-z\s-]+)$", part)
        if match2:
            food_items.append(match2.group(1).strip(" ."))
            quantities.append(1)
    return food_items, quantities

def _local_chat_response(message: str, session_id: str) -> str:
    text = message.strip().lower()

    if not text:
        return "Tell me what you'd like to eat, or ask to see the menu."

    if any(re.search(rf"\b{word}\b", text) for word in ("hello", "hi", "hey")):
        return "Hey there! I can show the menu, take your order, or track an order."

    if "menu" in text:
        return handle_show_menu()["fulfillmentText"]

    if "track" in text:
        match = re.search(r"\b\d+\b", text)
        return handle_track_order({"order_id": match.group(0) if match else None})["fulfillmentText"]

    if "cancel" in text:
        match = re.search(r"\b\d+\b", text)
        return handle_cancel_order({"order_id": match.group(0) if match else None})["fulfillmentText"]

    if "cart" in text or "summary" in text:
        return handle_cart_summary(session_id)["fulfillmentText"]

    if any(word in text for word in ("confirm", "place order", "complete order", "that's it", "that's all", "done", "finish", "checkout")):
        return handle_order_complete(session_id)["fulfillmentText"]
    
    if any(word in text for word in ("no", "nope", "nothing", "nevermind", "never mind", "nah")):
        return "Okay! Let me know if you need anything else."

    if text in ("i want to order", "i want to place an order", "new order", "order", "i want", "i would like to order"):
        return "Sure! Tell me what you'd like. Example: '2 burgers and 1 pizza'"

    food_items, quantities = _parse_order_items(text)
    if food_items:
        return handle_order_add(
            {"food_items": food_items, "number": quantities},
            session_id,
        )["fulfillmentText"]

    if "order" in text:
        return "Sure. Tell me the item and quantity, like '2 burgers and 1 pizza'."

    return "I can help with the menu, orders, tracking, and cancellations. What would you like to do?"


@app.post("/chat")
async def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())

    try:
        token = get_dialogflow_token()
        project_id = os.getenv("DIALOGFLOW_PROJECT_ID")
        url = (
            f"https://dialogflow.googleapis.com/v2/projects/{project_id}"
            f"/agent/sessions/{session_id}:detectIntent"
        )
        payload = {
            "queryInput": {
                "text": {"text": req.message, "languageCode": "en"}
            },
            "queryParams": {
                "timeZone": "Asia/Kolkata"
            }
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        result = response.json()
    except Exception:
        logger.exception("Dialogflow call failed; using local fallback")
        return _reply(_local_chat_response(req.message, session_id), session_id)

    query_result = result.get("queryResult", {})
    intent_name = query_result.get("intent", {}).get("displayName", "").strip().lower()
    parameters = query_result.get("parameters", {})

    logger.info("Chat intent: %s | session: %s", intent_name, session_id)

    # Route to handlers based on intent
    if intent_name == "order_add":
        reply = handle_order_add(parameters, session_id)["fulfillmentText"]

    elif "order.remove" in intent_name:
        reply = handle_order_remove(parameters, session_id)["fulfillmentText"]

    elif intent_name == "cart.summary":
        reply = handle_cart_summary(session_id)["fulfillmentText"]

    elif intent_name.startswith("order.complete"):
        reply = handle_order_complete(session_id)["fulfillmentText"]

    elif intent_name.startswith("track.order") or intent_name == "track order":
        reply = handle_track_order(parameters)["fulfillmentText"]

    elif intent_name in ("show.menu", "menu"):
        reply = handle_show_menu()["fulfillmentText"]

    elif intent_name == "order.cancel":
        reply = handle_cancel_order(parameters)["fulfillmentText"]

    elif intent_name in ("new order", "default welcome intent"):
        reply = query_result.get("fulfillmentText", "Welcome! Say 'show menu' to get started.")

    elif _is_dialogflow_fallback(intent_name):
        reply = _local_chat_response(req.message, session_id)

    else:
        
        cart = get_or_create_cart(session_id)
        if cart and intent_name == "default fallback intent":
           reply = handle_order_complete(session_id)["fulfillmentText"]
        else:
          reply = query_result.get("fulfillmentText") or "I didn't understand that. Try 'show menu' or '2 burgers'."

    return _reply(reply, session_id)
    
@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}





@app.get("/payment/callback")
async def payment_callback(
    razorpay_payment_id: str = Query(None),
    razorpay_payment_link_id: str = Query(None),
    razorpay_payment_link_reference_id: str = Query(None),
    razorpay_payment_link_status: str = Query(None),
    razorpay_signature: str = Query(None),
):
    """Razorpay redirects here after payment."""
    try:
        if razorpay_payment_link_status == "paid":
            # Extract order_id from reference
            order_id = razorpay_payment_link_reference_id

            # Update order status and payment details in DB
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE orders SET status = 'paid', payment_id = %s, payment_link_id = %s WHERE id = %s",
                (razorpay_payment_id, razorpay_payment_link_id, order_id)
            )
            conn.commit()
            cursor.close()
            conn.close()

            logger.info("Payment confirmed for order #%s", order_id)

            return HTMLResponse(content="""
                <html>
                <head>
                    <style>
                        body { font-family: sans-serif; text-align: center;
                               background: #0d0d0d; color: white; padding: 60px; }
                        .emoji { font-size: 80px; }
                        h1 { color: #f97316; }
                        p { color: #888; }
                    </style>
                </head>
                <body>
                    <div class="emoji">🎉</div>
                    <h1>Payment Successful!</h1>
                    <p>Your order has been confirmed.</p>
                    <p>Go back to <a href="https://gleaming-halva-bab9c6.netlify.app"
                       style="color:#f97316">FoodieBot</a></p>
                </body>
                </html>
            """)
        else:
            return HTMLResponse(content="""
                <html>
                <body style="font-family:sans-serif;text-align:center;
                             background:#0d0d0d;color:white;padding:60px">
                    <h1 style="color:red">Payment Failed</h1>
                    <p>Please try again.</p>
                </body>
                </html>
            """)

    except Exception:
        logger.exception("Payment callback error")
        return HTMLResponse(content="<h1>Error processing payment</h1>")






# ------------------------------------------
# 🔗 Dialogflow Webhook
# ------------------------------------------
def extract_session_id(body: dict) -> str:
    session = body.get("session", "")
    return session.split("/")[-1] if session else "default_session"


@app.post("/webhook")
async def dialogflow_webhook(request: Request):
    start = time.monotonic()
    body = await request.json()

    intent: str = body["queryResult"]["intent"]["displayName"].strip().lower()
    parameters: dict = body["queryResult"].get("parameters", {})
    session_id: str = extract_session_id(body)

    logger.info("Intent: %s | Session: %s | Params: %s", intent, session_id, parameters)

    if intent == "order_add":
        response = handle_order_add(parameters, session_id)
    elif "order.remove" in intent:
        response = handle_order_remove(parameters, session_id)
    elif intent == "cart.summary":
        response = handle_cart_summary(session_id)
    elif intent.startswith("order.complete"):
        response = handle_order_complete(session_id)
    elif intent.startswith("track.order"):
        response = handle_track_order(parameters)
    elif intent == "show.menu" or intent == "menu":
        response = handle_show_menu()
    elif intent == "order.cancel":
        response = handle_cancel_order(parameters)
    else:
        logger.warning("Unhandled intent: %s", intent)
        response = {"fulfillmentText": f"Sorry, I don't understand '{intent}' yet."}

    elapsed_ms = (time.monotonic() - start) * 1000
    logger.info("Response time: %.1fms", elapsed_ms)

    return JSONResponse(content=response)
