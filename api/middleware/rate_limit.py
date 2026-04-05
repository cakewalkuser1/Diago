"""
Simple in-memory rate limiter per user tier.

For production, replace with Redis-backed rate limiting.
"""

import logging
import time
from collections import defaultdict
from typing import Optional

from fastapi import Depends, HTTPException, Request

from api.middleware.auth import AuthenticatedUser, UserTier, get_optional_user

logger = logging.getLogger(__name__)

# ─── Rate Limit Configuration ───
# Product: diagnoses per calendar month per tier.
# Stripe price IDs: DIAGO_STRIPE_DIY_PRICE_ID, DIAGO_STRIPE_PRO_MECHANIC_PRICE_ID, DIAGO_STRIPE_SHOP_PRICE_ID (core/config).

TIER_LIMITS = {
    UserTier.FREE: 3,
    UserTier.DIY: 50,
    UserTier.PRO_MECHANIC: 500,
    UserTier.SHOP: 10000,  # effectively unlimited
}

# In-memory fallback when DB not available (e.g. tests)
_counters: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))


def _month_key() -> str:
    """Current month key for rate limiting."""
    t = time.gmtime()
    return f"{t.tm_year}-{t.tm_mon:02d}"


def _get_used(key: str, month: str) -> int:
    """Get current usage count; prefer DB, fallback to in-memory."""
    try:
        from api.deps import get_db_manager
        db = get_db_manager()
        return db.get_diagnosis_usage(key, month)
    except Exception:
        return _counters[key][month]


def _increment_used(key: str, month: str) -> None:
    """Increment usage; prefer DB, then keep in-memory in sync."""
    try:
        from api.deps import get_db_manager
        db = get_db_manager()
        db.increment_diagnosis_usage(key, month)
        _counters[key][month] = db.get_diagnosis_usage(key, month)
    except Exception:
        _counters[key][month] += 1


def check_diagnosis_rate_limit(
    user: Optional[AuthenticatedUser] = None,
    client_ip: str = "unknown",
) -> None:
    """
    Check if the user has exceeded their monthly diagnosis limit.

    Raises HTTPException 429 if over limit.
    """
    from core.config import get_settings
    if get_settings().disable_diagnosis_rate_limit:
        return  # developer bypass
    tier = user.tier if user else UserTier.FREE
    limit = TIER_LIMITS[tier]
    key = user.user_id if user else f"anon:{client_ip}"
    month = _month_key()

    current = _get_used(key, month)
    if current >= limit:
        raise HTTPException(
            status_code=429,
            detail=f"Monthly diagnosis limit reached ({limit} for {tier.value} tier). Upgrade for more.",
        )


def increment_diagnosis_count(
    user: Optional[AuthenticatedUser] = None,
    client_ip: str = "unknown",
) -> None:
    """Increment the diagnosis counter after a successful diagnosis."""
    key = user.user_id if user else f"anon:{client_ip}"
    month = _month_key()
    _increment_used(key, month)


def get_remaining_diagnoses(
    user: Optional[AuthenticatedUser] = None,
    client_ip: str = "unknown",
) -> dict:
    """Get remaining diagnosis count for the current month."""
    tier = user.tier if user else UserTier.FREE
    limit = TIER_LIMITS[tier]
    key = user.user_id if user else f"anon:{client_ip}"
    month = _month_key()
    used = _get_used(key, month)

    return {
        "tier": tier.value,
        "limit": limit,
        "used": used,
        "remaining": max(0, limit - used),
    }
