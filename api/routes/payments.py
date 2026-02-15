"""
Payment API Routes
Endpoints for Stripe subscription management and webhooks.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.middleware.auth import (
    AuthenticatedUser,
    UserTier,
    get_current_user,
)
from api.middleware.rate_limit import get_remaining_diagnoses
from api.payments.stripe_service import (
    create_checkout_session,
    cancel_subscription,
    get_customer_subscription,
    process_webhook_event,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ─── Models ───

class CheckoutRequest(BaseModel):
    tier: str  # "pro" or "premium"
    success_url: str
    cancel_url: str


class CheckoutResponse(BaseModel):
    checkout_url: str


class SubscriptionResponse(BaseModel):
    tier: str
    limit: int
    used: int
    remaining: int


# ─── Endpoints ───

@router.post("/checkout", response_model=CheckoutResponse)
async def create_checkout(
    request: CheckoutRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Create a Stripe Checkout Session for upgrading to a paid tier."""
    try:
        tier = UserTier(request.tier)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid tier: {request.tier}")

    if tier == UserTier.FREE:
        raise HTTPException(status_code=400, detail="Cannot checkout for free tier")

    try:
        url = create_checkout_session(
            user_id=user.user_id,
            user_email=user.email or "",
            tier=tier,
            success_url=request.success_url,
            cancel_url=request.cancel_url,
        )
        return CheckoutResponse(checkout_url=url)
    except Exception as e:
        logger.error("Checkout creation failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to create checkout session")


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription_status(
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Get the current user's subscription status and usage."""
    usage = get_remaining_diagnoses(user=user)
    return SubscriptionResponse(**usage)


@router.post("/cancel")
async def cancel_user_subscription(
    user: AuthenticatedUser = Depends(get_current_user),
):
    """Cancel the current user's subscription at end of billing period."""
    from api.deps import get_db_manager
    from api.payments.stripe_service import cancel_subscription

    db = get_db_manager()
    subscription_id = db.get_subscription_id_by_user_id(user.user_id)
    if not subscription_id:
        raise HTTPException(
            status_code=404,
            detail="No active subscription found for this account.",
        )
    try:
        cancel_subscription(subscription_id)
        return {"message": "Subscription will cancel at the end of the billing period."}
    except Exception as e:
        logger.error("Cancel subscription failed: %s", e)
        raise HTTPException(status_code=500, detail="Failed to cancel subscription")


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Stripe webhook endpoint.

    Receives events from Stripe (subscription changes, payments, etc.)
    and updates user tiers in Supabase accordingly.
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        result = process_webhook_event(payload, sig_header)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    if result["handled"]:
        action = result.get("action")
        logger.info("Webhook processed: action=%s", action)

        if action == "activate_subscription":
            user_id = result.get("user_id")
            tier = result.get("tier")
            subscription_id = result.get("subscription_id")
            if user_id and tier:
                from api.supabase_admin import update_user_tier
                update_user_tier(user_id, tier)
            if subscription_id and user_id:
                try:
                    from api.deps import get_db_manager
                    get_db_manager().save_stripe_subscription_user(subscription_id, user_id)
                except Exception as e:
                    logger.warning("Could not save subscription mapping: %s", e)

        elif action == "deactivate_subscription":
            subscription_id = result.get("subscription_id")
            if subscription_id:
                try:
                    from api.deps import get_db_manager
                    from api.supabase_admin import update_user_tier
                    db = get_db_manager()
                    user_id = db.get_user_id_by_subscription_id(subscription_id)
                    if user_id:
                        update_user_tier(user_id, "free")
                        db.delete_stripe_subscription_user(subscription_id)
                except Exception as e:
                    logger.warning("Could not sync tier on cancel: %s", e)

    return {"received": True}
