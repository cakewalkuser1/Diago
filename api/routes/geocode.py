"""
Geocoding API: address -> lat/lng via Nominatim (OpenStreetMap).
Used for dispatch flow when user enters address instead of using geolocation.
"""

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter()

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "Diago/1.0 (automotive diagnostics app)"


@router.get("/geocode")
async def geocode_address(address: str) -> dict:
    """
    Geocode an address to lat/lng using Nominatim (OpenStreetMap).
    Returns { "latitude": float, "longitude": float } or 404 if not found.
    """
    if not address or not address.strip():
        raise HTTPException(status_code=400, detail="address is required")

    params = {
        "q": address.strip(),
        "format": "json",
        "limit": 1,
    }
    headers = {"User-Agent": USER_AGENT}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(NOMINATIM_URL, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as e:
        logger.warning("Geocoding request failed: %s", e)
        raise HTTPException(status_code=502, detail="Geocoding service unavailable") from e

    if not data:
        raise HTTPException(status_code=404, detail="Address not found")

    try:
        lat = float(data[0]["lat"])
        lon = float(data[0]["lon"])
    except (KeyError, TypeError, ValueError) as e:
        logger.warning("Invalid geocode response: %s", e)
        raise HTTPException(status_code=502, detail="Invalid geocoding response") from e

    return {"latitude": lat, "longitude": lon}
