# main.py

import logging
import os
import time

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

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


def extract_session_id(body: dict) -> str:
    session = body.get("session", "")
    return session.split("/")[-1] if session else "default_session"


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}


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