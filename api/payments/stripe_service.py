"""
Stripe payment integration service.

Handles subscription management, checkout sessions, and webhook processing.
Uses Stripe standard API keys (STRIPE_SECRET_KEY / STRIPE_PUBLISHABLE_KEY).
Do not use legacy API keys; use the keys from Dashboard → Developers → API keys after disabling legacy.
"""

import logging
from typing import Optional

import stripe

from core.config import get_settings
from api.middleware.auth import UserTier

logger = logging.getLogger(__name__)

# ─── Tier → Stripe Price Mapping ───
# Price IDs are loaded from config (DIAGO_STRIPE_DIY_PRICE_ID, DIAGO_STRIPE_PRO_MECHANIC_PRICE_ID, DIAGO_STRIPE_SHOP_PRICE_ID).


def _get_tier_price_id(tier: UserTier) -> str:
    """Return the Stripe Price ID for the given tier from config."""
    settings = get_settings()
    if tier == UserTier.DIY:
        return settings.stripe_diy_price_id or ""
    if tier == UserTier.PRO_MECHANIC:
        return settings.stripe_pro_mechanic_price_id or ""
    if tier == UserTier.SHOP:
        return settings.stripe_shop_price_id or ""
    return ""


def _get_stripe_client() -> stripe.StripeClient:
    """Get configured Stripe client. Use standard secret key from Stripe Dashboard (not legacy)."""
    settings = get_settings()
    api_key = settings.stripe_secret_key
    if not api_key:
        raise RuntimeError("Stripe API key not configured")
    return stripe.StripeClient(api_key=api_key)


# ─── Checkout ───

def create_checkout_session(
    user_id: str,
    user_email: str,
    tier: UserTier,
    success_url: str,
    cancel_url: str,
) -> str:
    """
    Create a Stripe Checkout Session for a subscription.

    Returns the checkout session URL.
    """
    client = _get_stripe_client()
    price_id = _get_tier_price_id(tier)
    if not price_id:
        raise ValueError(f"No Stripe price configured for tier: {tier}")

    session = client.checkout.sessions.create(
        params={
            "mode": "subscription",
            "customer_email": user_email,
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": {"user_id": user_id, "tier": tier.value},
        }
    )

    logger.info("Created checkout session for user %s, tier %s", user_id, tier.value)
    return session.url


# ─── Subscription Management ───

def get_customer_subscription(customer_id: str) -> Optional[dict]:
    """Get the active subscription for a Stripe customer."""
    client = _get_stripe_client()
    subscriptions = client.subscriptions.list(
        params={"customer": customer_id, "status": "active", "limit": 1}
    )

    if subscriptions.data:
        sub = subscriptions.data[0]
        return {
            "id": sub.id,
            "status": sub.status,
            "current_period_end": sub.current_period_end,
            "cancel_at_period_end": sub.cancel_at_period_end,
        }
    return None


def create_part_payment_intent(
    part_description: str,
    retailer: str,
    retailer_store_id: str,
    user_id: str | None = None,
) -> dict:
    """
    Create a Stripe PaymentIntent for a parts order.
    Returns { client_secret, payment_intent_id, amount_cents }.
    Order is created separately with this payment_intent_id.
    """
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise RuntimeError("Stripe API key not configured")
    amount_cents = settings.stripe_part_price_cents or 4999

    client = _get_stripe_client()
    pi = client.payment_intents.create(
        params={
            "amount": amount_cents,
            "currency": "usd",
            "metadata": {
                "part_description": part_description[:200],
                "retailer": retailer[:100],
                "user_id": (user_id or "")[:100],
            },
        }
    )
    logger.info("Created PaymentIntent %s for parts", pi.id)
    return {
        "client_secret": pi.client_secret,
        "payment_intent_id": pi.id,
        "amount_cents": amount_cents,
    }


def get_payment_intent_status(payment_intent_id: str) -> str | None:
    """Return PaymentIntent status (succeeded, processing, etc.) or None if error."""
    try:
        client = _get_stripe_client()
        pi = client.payment_intents.retrieve(payment_intent_id)
        return pi.status
    except Exception as e:
        logger.warning("Failed to retrieve PaymentIntent %s: %s", payment_intent_id, e)
        return None


def cancel_subscription(subscription_id: str) -> dict:
    """Cancel a subscription at the end of the billing period."""
    client = _get_stripe_client()
    sub = client.subscriptions.update(
        subscription_id,
        params={"cancel_at_period_end": True},
    )
    logger.info("Subscription %s set to cancel at period end", subscription_id)
    return {"status": sub.status, "cancel_at_period_end": sub.cancel_at_period_end}


# ─── Webhook Processing ───

def process_webhook_event(payload: bytes, sig_header: str) -> dict:
    """
    Process a Stripe webhook event.

    Validates the webhook signature and handles subscription events.
    Returns a dict with the event type and any relevant data.
    """
    settings = get_settings()
    endpoint_secret = settings.stripe_webhook_secret

    if not endpoint_secret:
        raise RuntimeError("Stripe webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except stripe.SignatureVerificationError:
        raise ValueError("Invalid webhook signature")

    event_type = event["type"]
    data = event["data"]["object"]

    result = {"event_type": event_type, "handled": False}

    if event_type == "checkout.session.completed":
        # New subscription created
        user_id = data.get("metadata", {}).get("user_id")
        tier = data.get("metadata", {}).get("tier")
        customer_id = data.get("customer")
        subscription_id = data.get("subscription")  # Stripe subscription id
        logger.info(
            "Checkout completed: user=%s tier=%s customer=%s sub=%s",
            user_id, tier, customer_id, subscription_id,
        )
        result.update({
            "handled": True,
            "user_id": user_id,
            "tier": tier,
            "customer_id": customer_id,
            "subscription_id": subscription_id,
            "action": "activate_subscription",
        })

    elif event_type == "customer.subscription.updated":
        sub_id = data.get("id")
        status = data.get("status")
        logger.info("Subscription updated: %s status=%s", sub_id, status)
        result.update({
            "handled": True,
            "subscription_id": sub_id,
            "status": status,
            "action": "update_subscription",
        })

    elif event_type == "customer.subscription.deleted":
        sub_id = data.get("id")
        logger.info("Subscription deleted: %s", sub_id)
        result.update({
            "handled": True,
            "subscription_id": sub_id,
            "action": "deactivate_subscription",
        })

    elif event_type == "invoice.payment_failed":
        customer_id = data.get("customer")
        logger.warning("Payment failed for customer %s", customer_id)
        result.update({
            "handled": True,
            "customer_id": customer_id,
            "action": "payment_failed",
        })

    elif event_type == "payment_intent.succeeded":
        payment_intent_id = data.get("id")
        result.update({
            "handled": True,
            "payment_intent_id": payment_intent_id,
            "action": "part_payment_succeeded",
        })
        logger.info("Part payment succeeded: pi=%s", payment_intent_id)

    return result
