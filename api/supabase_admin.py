"""
Supabase Auth Admin API helpers.
Updates user app_metadata (e.g. tier) from backend (Stripe webhook).
Requires SUPABASE_SERVICE_ROLE_KEY and SUPABASE_URL.
"""

import logging
from typing import Any

from core.config import get_settings

logger = logging.getLogger(__name__)


def update_user_app_metadata(user_id: str, app_metadata: dict[str, Any]) -> bool:
    """
    Update a user's app_metadata via Supabase Auth Admin API.
    Returns True on success, False if config missing or request failed.
    """
    settings = get_settings()
    url = settings.supabase_url
    key = settings.supabase_service_role_key
    if not url or not key:
        logger.warning("Supabase URL or service role key not set; skipping app_metadata update")
        return False
    url = url.rstrip("/")
    if not url.endswith("/auth/v1"):
        url = f"{url}/auth/v1"
    admin_url = f"{url}/admin/users/{user_id}"
    try:
        import httpx
        with httpx.Client(timeout=10.0) as client:
            r = client.patch(
                admin_url,
                headers={
                    "apikey": key,
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={"app_metadata": app_metadata},
            )
            if r.is_success:
                logger.info("Updated app_metadata for user %s", user_id)
                return True
            logger.warning("Supabase admin PATCH failed: %s %s", r.status_code, r.text)
            return False
    except Exception as e:
        logger.warning("Supabase admin update failed: %s", e)
        return False


def update_user_tier(user_id: str, tier: str) -> bool:
    """Set user's tier in app_metadata (free, pro, premium)."""
    return update_user_app_metadata(user_id, {"tier": tier})
