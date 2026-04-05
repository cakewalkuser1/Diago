"""
Mechanic Profile API
Register, update, and manage mechanic profiles.
"""

import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Header, UploadFile
from pydantic import BaseModel, Field

from api.deps import get_db_manager
from core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()

ALLOWED_PHOTO_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_PHOTO_SIZE = 5 * 1024 * 1024  # 5 MB


def _get_user_id(x_mechanic_user_id: Optional[str] = Header(None)) -> str:
    """Resolve user_id from header (dev) or generate anon id."""
    if x_mechanic_user_id:
        return x_mechanic_user_id
    return "anon-mechanic"


class MechanicRegisterRequest(BaseModel):
    """Register a new mechanic profile."""
    name: str = Field(..., min_length=1)
    email: str = ""
    phone: str = ""
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    service_radius_mi: float = 25.0
    hourly_rate_cents: Optional[int] = None
    bio: str = ""
    skills: str = ""


class MechanicUpdateRequest(BaseModel):
    """Update mechanic profile (partial)."""
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    service_radius_mi: Optional[float] = None
    hourly_rate_cents: Optional[int] = None
    bio: Optional[str] = None
    skills: Optional[str] = None
    availability: Optional[str] = None


@router.post("/register", response_model=dict)
async def register_mechanic(
    request: MechanicRegisterRequest,
    user_id: str = Depends(_get_user_id),
    db=Depends(get_db_manager),
):
    """Register as a mechanic. Requires user_id (X-Mechanic-User-Id header or anon)."""
    existing = db.get_mechanic_by_user_id(user_id)
    if existing:
        raise HTTPException(status_code=400, detail="Already registered as mechanic")
    mid = db.create_mechanic_profile(
        user_id=user_id,
        name=request.name,
        email=request.email,
        phone=request.phone,
        latitude=request.latitude,
        longitude=request.longitude,
        service_radius_mi=request.service_radius_mi,
        hourly_rate_cents=request.hourly_rate_cents,
        bio=request.bio,
        skills=request.skills,
    )
    return {"mechanic_id": mid, "message": "Registered successfully"}


@router.get("/me", response_model=dict)
async def get_my_profile(
    user_id: str = Depends(_get_user_id),
    db=Depends(get_db_manager),
):
    """Get current user's mechanic profile."""
    m = db.get_mechanic_by_user_id(user_id)
    if not m:
        raise HTTPException(status_code=404, detail="Not registered as mechanic")
    return m


@router.put("/me", response_model=dict)
async def update_my_profile(
    request: MechanicUpdateRequest,
    user_id: str = Depends(_get_user_id),
    db=Depends(get_db_manager),
):
    """Update current mechanic profile."""
    m = db.get_mechanic_by_user_id(user_id)
    if not m:
        raise HTTPException(status_code=404, detail="Not registered as mechanic")
    updates = {k: v for k, v in request.model_dump(exclude_unset=True).items() if v is not None}
    if not updates:
        return m
    db.update_mechanic_profile(m["id"], **updates)
    return db.get_mechanic_by_id(m["id"]) or m


@router.post("/me/photo", response_model=dict)
async def upload_profile_photo(
    file: UploadFile = File(...),
    user_id: str = Depends(_get_user_id),
    db=Depends(get_db_manager),
):
    """Upload profile photo. Returns updated profile with profile_photo_url."""
    if file.content_type not in ALLOWED_PHOTO_TYPES:
        raise HTTPException(status_code=400, detail="Invalid content type. Use JPEG, PNG, or WebP")
    content = await file.read()
    if len(content) > MAX_PHOTO_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 5 MB)")
    ext = ".jpg" if file.content_type == "image/jpeg" else ".png" if file.content_type == "image/png" else ".webp"
    photo_id = f"mechanic-{str(uuid.uuid4())[:8]}{ext}"
    settings = get_settings()
    uploads_dir = Path(settings.user_data_dir) / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    (uploads_dir / photo_id).write_bytes(content)
    url = f"/uploads/{photo_id}"
    m = db.get_mechanic_by_user_id(user_id)
    if not m:
        raise HTTPException(status_code=404, detail="Not registered as mechanic")
    db.update_mechanic_profile(m["id"], profile_photo_url=url)
    return {"profile_photo_url": url, "mechanic": db.get_mechanic_by_id(m["id"]) or m}
