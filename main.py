import asyncio
import hashlib
import hmac
import httpx
import json
import secrets

from datetime import datetime, timezone
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, HttpUrl

app = FastAPI(
    servers=[
        {"url": "http://localhost:8000", "description": "localhost server"},
    ],
)

webhooks: dict[str, str] = {}  # url -> secret


class WebhookRegistration(BaseModel):
    url: HttpUrl


@app.post("/register-webhook")
async def register_webhook(webhook: WebhookRegistration):
    secret = secrets.token_hex(32)
    webhooks[webhook.url] = secret
    return {"status": "registered", "url": webhook.url, "secret": secret}


def sign_payload(secret: str, payload: bytes) -> str:
    return hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


async def send_webhook(url: str, secret: str, event_type: str, payload: dict):
    timestamp = datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')
    body = json.dumps({
        "type": event_type,
        "timestamp": timestamp,
        "data": payload,
    }).encode()
    signature = sign_payload(secret, body)
    headers = {
        "Content-Type": "application/json",
        "X-Signature-256": f"sha256={signature}",
        "webhook-timestamp": timestamp,
        "webhook-id": secrets.token_hex(32),
        #"webhook-signature": ,
    }
    async with httpx.AsyncClient() as client:
        await client.post(url, content=body, headers=headers)


async def dispatch_webhooks():
    while True:
        await asyncio.sleep(5)
        payload = {"event": "ping", "data": "Hello webhook!"}
        for url, secret in webhooks.items():
            try:
                await send_webhook(str(url), secret, "ping", {"text": "Hello webhook!"})
            except Exception as e:
                print(f"Failed to send to {url}: {e}")


@app.on_event("startup")
async def start():
    asyncio.create_task(dispatch_webhooks())
