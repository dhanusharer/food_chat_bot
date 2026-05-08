# main.py

import json
import logging
import os
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


@app.post("/chat")
async def chat(req: ChatRequest):
    session_id = req.session_id or str(uuid.uuid4())
    project_id = os.getenv("DIALOGFLOW_PROJECT_ID")

    try:
        token = get_dialogflow_token()
        url = (
            f"https://dialogflow.googleapis.com/v2/projects/{project_id}"
            f"/agent/sessions/{session_id}:detectIntent"
        )
        payload = {
            "queryInput": {
                "text": {"text": req.message, "languageCode": "en"}
            }
        }
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        result = response.json()
        reply = result["queryResult"]["fulfillmentText"]
        return JSONResponse({"response": reply, "session_id": session_id})

    except Exception as e:
        logger.exception("Dialogflow call failed")
        return JSONResponse({"response": "Sorry, something went wrong.", "session_id": session_id})


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
