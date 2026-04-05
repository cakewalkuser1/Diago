"""
Supabase JWT authentication middleware.

Validates Supabase-issued JWTs, extracts user info and subscription tier,
and attaches them to the request state for downstream route handlers.
"""

import logging
from enum import Enum
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from core.config import get_settings

logger = logging.getLogger(__name__)

# Bearer token extractor
_bearer_scheme = HTTPBearer(auto_error=False)


# ─── User Tiers ───
class UserTier(str, Enum):
    FREE = "free"
    DIY = "diy"
    PRO_MECHANIC = "pro_mechanic"
    SHOP = "shop"


class AuthenticatedUser(BaseModel):
    """Authenticated user info extracted from JWT."""

    user_id: str
    email: Optional[str] = None
    tier: UserTier = UserTier.FREE
    raw_claims: dict = {}


# ─── JWT Validation ───

def _decode_supabase_jwt(token: str) -> dict:
    """
    Decode and validate a Supabase-issued JWT.

    Supabase uses HS256 with the project's JWT secret.
    The JWT contains `sub` (user ID), `email`, and custom `app_metadata`.
    """
    settings = get_settings()
    jwt_secret = settings.supabase_jwt_secret

    if not jwt_secret:
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: JWT secret not set",
        )

    try:
        payload = jwt.decode(
            token,
            jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        logger.warning("Invalid JWT: %s", e)
        raise HTTPException(status_code=401, detail="Invalid token")


def _extract_tier(claims: dict) -> UserTier:
    """Extract user tier from JWT claims (set via Supabase app_metadata)."""
    app_metadata = claims.get("app_metadata", {})
    tier_str = app_metadata.get("tier", "free")
    try:
        return UserTier(tier_str)
    except ValueError:
        return UserTier.FREE


# ─── FastAPI Dependencies ───

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> AuthenticatedUser:
    """
    FastAPI dependency: extract and validate the current user from the JWT.

    Usage:
        @router.get("/protected")
        async def protected_route(user: AuthenticatedUser = Depends(get_current_user)):
            ...
    """
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    claims = _decode_supabase_jwt(credentials.credentials)

    return AuthenticatedUser(
        user_id=claims.get("sub", ""),
        email=claims.get("email"),
        tier=_extract_tier(claims),
        raw_claims=claims,
    )


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> Optional[AuthenticatedUser]:
    """
    FastAPI dependency: optionally extract the user. Returns None if no token.

    Useful for endpoints that work with or without authentication
    (e.g., free tier with limited features).
    """
    if credentials is None:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


def requires_tier(*allowed_tiers: UserTier):
    """
    FastAPI dependency factory: restrict endpoint to specific tiers.

    Usage:
        @router.get("/premium-feature")
        async def premium(user: AuthenticatedUser = Depends(requires_tier(UserTier.DIY, UserTier.PRO_MECHANIC, UserTier.SHOP))):
            ...
    """

    async def _check_tier(
        user: AuthenticatedUser = Depends(get_current_user),
    ) -> AuthenticatedUser:
        if user.tier not in allowed_tiers:
            raise HTTPException(
                status_code=403,
                detail=f"This feature requires one of: {', '.join(t.value for t in allowed_tiers)}",
            )
        return user

    return _check_tier
