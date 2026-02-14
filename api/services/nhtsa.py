"""
NHTSA API client: VIN decode (vPIC) and Recalls (api.nhtsa.gov).
All endpoints are free; no API key required. Respect rate limits.
"""

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

VPIC_BASE = "https://vpic.nhtsa.dot.gov/api"
NHTSA_BASE = "https://api.nhtsa.gov"


def decode_vin(vin: str, model_year: int | None = None) -> dict[str, Any]:
    """
    Decode a VIN using NHTSA vPIC. Returns flat key-value pairs.

    Args:
        vin: 17-character VIN (partial supported with * for unknown).
        model_year: Optional model year for better decoding.

    Returns:
        Dict with keys like Make, Model, ModelYear, EngineModel, etc.
        Includes "Message" and "Results" from vPIC; we return the first
        Result's flat dict or empty dict on failure.
    """
    vin = (vin or "").strip().upper()
    if not vin:
        return {"error": "VIN is required"}

    url = f"{VPIC_BASE}/vehicles/DecodeVinValues/{vin}"
    params = {"format": "json"}
    if model_year is not None:
        params["modelyear"] = model_year

    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning("vPIC decode failed for VIN %s: %s", vin[:8], e)
        return {"error": str(e)}

    results = data.get("Results") or []
    if not results:
        return {"error": "No decode results", "Message": data.get("Message", "")}

    # vPIC DecodeVinValues returns a list of one flat object
    return results[0]


def recalls_by_vehicle(make: str, model: str, model_year: int) -> list[dict[str, Any]]:
    """
    Get NHTSA recalls for a vehicle by year, make, model.

    Args:
        make: Make (e.g. Honda, Acura).
        model: Model (e.g. Accord, RDX).
        model_year: Model year (e.g. 2012).

    Returns:
        List of recall objects from NHTSA (campaign number, summary, etc.).
    """
    if not make or not model or not model_year:
        return []

    url = f"{NHTSA_BASE}/recalls/recallsByVehicle"
    params = {
        "make": make.strip(),
        "model": model.strip(),
        "modelYear": int(model_year),
    }

    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning("NHTSA recalls failed for %s %s %s: %s", make, model, model_year, e)
        return []

    # API returns { "Count": N, "Results": [ ... ] } or similar
    results = data.get("results") or data.get("Results") or []
    return results if isinstance(results, list) else []


def get_vehicle_years() -> list[int]:
    """Return list of model years from 1996 to current+1 (OBD-II era)."""
    from datetime import datetime
    current = datetime.now().year
    return list(range(1996, current + 2))


# NHTSA vehicle types (safe for URL path segment)
_VALID_VEHICLE_TYPES = frozenset({"car", "truck", "multipurpose passenger vehicle", "bus", "trailer", "motorcycle", "low speed vehicle", "incomplete vehicle"})


def get_makes_for_vehicle_type(vehicle_type: str = "car") -> list[dict[str, Any]]:
    """
    Get makes for a vehicle type (e.g. car, truck). Returns list of {MakeId, MakeName}.
    """
    # Restrict to known types to avoid injecting into URL path
    normalized = (vehicle_type or "car").strip().lower()
    if normalized not in _VALID_VEHICLE_TYPES:
        normalized = "car"
    url = f"{VPIC_BASE}/vehicles/GetMakesForVehicleType/{normalized}"
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(url, params={"format": "json"})
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning("GetMakesForVehicleType failed: %s", e)
        return []
    results = data.get("Results") or []
    if not isinstance(results, list):
        return []
    return [
        {"make_id": r.get("MakeId") or r.get("Make_ID"), "make_name": (r.get("MakeName") or r.get("Make_Name") or "").strip()}
        for r in results
        if (r.get("MakeId") or r.get("Make_ID")) is not None
    ]


def get_models_for_make_id_year(make_id: int, model_year: int) -> list[dict[str, Any]]:
    """
    Get models for a make and model year. Returns list of {Model_ID, Model_Name, Make_ID, Make_Name}.
    """
    if not make_id or model_year < 1995:
        return []
    url = f"{VPIC_BASE}/vehicles/GetModelsForMakeIdYear/makeId/{make_id}/modelyear/{model_year}"
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(url, params={"format": "json"})
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning("GetModelsForMakeIdYear failed: %s", e)
        return []
    results = data.get("Results") or []
    if not isinstance(results, list):
        return []
    return [
        {
            "model_id": r.get("Model_ID") or r.get("ModelId"),
            "model_name": (r.get("Model_Name") or r.get("ModelName") or "").strip(),
            "make_id": r.get("Make_ID") or r.get("MakeId"),
            "make_name": (r.get("Make_Name") or r.get("MakeName") or "").strip(),
        }
        for r in results
    ]
