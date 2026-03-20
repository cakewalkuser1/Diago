"""
Push Notifications API: subscribe for job pings (mechanics).
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field

from api.deps import get_db_manager
from core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_user_id(x_user_id: Optional[str] = Header(None)) -> str:
    return x_user_id or "anon"


class PushSubscriptionRequest(BaseModel):
    """Web Push subscription from browser."""
    endpoint: str = Field(..., min_length=1)
    keys: dict = Field(..., description="p256dh and auth keys")
    expirationTime: Optional[int] = None


@router.post("/subscribe", response_model=dict)
async def subscribe_push(
    request: PushSubscriptionRequest,
    user_id: str = Depends(_get_user_id),
    db=Depends(get_db_manager),
):
    """
    Store push subscription for a user (mechanic).
    Called when user grants notification permission.
    """
    p256dh = (request.keys or {}).get("p256dh")
    auth = (request.keys or {}).get("auth")
    if not p256dh or not auth:
        raise HTTPException(status_code=400, detail="Missing p256dh or auth keys")
    try:
        db.connection.execute(
            """INSERT INTO push_subscriptions (user_id, endpoint, p256dh_key, auth_key)
               VALUES (?, ?, ?, ?)""",
            (user_id, request.endpoint, p256dh, auth),
        )
        db.connection.commit()
    except Exception as e:
        logger.warning("Push subscribe failed: %s", e)
        raise HTTPException(status_code=500, detail="Could not save subscription")
    return {"ok": True}


def send_push_to_user(user_id: str, title: str, body: str, data: Optional[dict] = None) -> int:
    """
    Send push notification to all subscriptions for user_id.
    Returns count of successful sends.
    """
    from api.deps import get_db_manager
    db = get_db_manager()
    cursor = db.connection.execute(
        "SELECT endpoint, p256dh_key, auth_key FROM push_subscriptions WHERE user_id = ?",
        (user_id,),
    )
    rows = cursor.fetchall()
    if not rows:
        return 0
    settings = get_settings()
    vapid_private = settings.vapid_private_key or ""
    if not vapid_private:
        logger.debug("VAPID not configured; skipping push")
        return 0
    try:
        from pywebpush import webpush, WebPushException
    except ImportError:
        logger.debug("pywebpush not installed; skipping push")
        return 0
    payload = json.dumps({"title": title, "body": body, "data": data or {}})
    sent = 0
    for row in rows:
        try:
            webpush(
                subscription_info={
                    "endpoint": row["endpoint"],
                    "keys": {"p256dh": row["p256dh_key"], "auth": row["auth_key"]},
                },
                data=payload,
                vapid_private_key=vapid_private,
                vapid_claims={"sub": "mailto:support@diago.app"},
            )
            sent += 1
        except Exception as e:
            logger.warning("Push send failed: %s", e)
    return sent
