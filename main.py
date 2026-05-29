# main.py

import json
import logging
import os
import re
import time
import uuid

import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import service_account
from pydantic import BaseModel

from handlers import (
    handle_cancel_order,
    handle_cart_summary,
    handle_order_add,
    handle_order_complete,
    handle_order_remove,
    handle_show_menu,
    handle_track_order,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="FoodieBot Webhook", version="1.0.0")

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


def _parse_order_items(text: str) -> tuple[list[str], list[int]]:
    text = text.lower().strip()
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

    if any(word in text for word in ("hello", "hi", "hey")):
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
    reply = _local_chat_response(req.message, session_id)
    return _reply(reply, session_id)
# ------------------------------------------
# ❤️ Health
# ------------------------------------------
@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}


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
