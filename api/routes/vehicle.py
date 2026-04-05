"""
Vehicle API Routes
VIN decode (NHTSA vPIC) and recalls (NHTSA).
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from pydantic import BaseModel, Field

from api.deps import get_db_manager
from api.services import nhtsa as nhtsa_service
from api.services import charm_li as charm_li_service

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class VinDecodeResponse(BaseModel):
    """VIN decode result (key fields + raw)."""
    make: str = ""
    model: str = ""
    model_year: str = ""
    trim: str = ""
    engine_model: str = ""
    vehicle_type: str = ""
    raw: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class RecallItem(BaseModel):
    """Single recall summary."""
    campaign_number: str = ""
    summary: str = ""
    consequence: str = ""
    remedy: str = ""
    component: str = ""
    nhtsa_id: str = ""


class RecallsResponse(BaseModel):
    """Recalls for a vehicle."""
    make: str
    model: str
    model_year: int
    count: int
    recalls: list[RecallItem]


class MakeItem(BaseModel):
    """Single make for dropdown."""
    make_id: int
    make_name: str


class ModelItem(BaseModel):
    """Single model for dropdown."""
    model_id: int
    model_name: str
    make_id: int
    make_name: str


class YearsResponse(BaseModel):
    """List of model years."""
    years: list[int]


class MakesResponse(BaseModel):
    """List of makes for a vehicle type."""
    makes: list[MakeItem]


class ModelsResponse(BaseModel):
    """List of models for make + year."""
    models: list[ModelItem]


class SelectedVehicleResponse(BaseModel):
    """Stored selected vehicle (for tailored diagnosis)."""
    model_year: int | None = None
    make: str = ""
    model: str = ""
    submodel: str = ""


class ManualUrlResponse(BaseModel):
    """charm.li (Operation CHARM) service manual URL for the vehicle; open in browser."""
    url: str | None = None
    make: str = ""
    model_year: int | None = None
    message: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _map_recall(item: dict) -> RecallItem:
    """Map NHTSA recall result to our model."""
    return RecallItem(
        campaign_number=str(item.get("campaignNumber") or item.get("NHTSACampaignNumber") or ""),
        summary=str(item.get("summary") or item.get("Summary") or ""),
        consequence=str(item.get("consequence") or item.get("Consequence") or ""),
        remedy=str(item.get("remedy") or item.get("Remedy") or ""),
        component=str(item.get("component") or item.get("Component") or ""),
        nhtsa_id=str(item.get("nhtsaId") or item.get("NHTSACampaignID") or ""),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/vin/{vin}", response_model=VinDecodeResponse)
async def decode_vin(
    vin: str,
    model_year: int | None = Query(None, description="Optional model year for better decode"),
):
    """Decode a VIN using NHTSA vPIC. Returns make, model, year, and raw decode."""
    result = nhtsa_service.decode_vin(vin, model_year)

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    # vPIC flat keys are typically PascalCase
    make = result.get("Make") or result.get("make") or ""
    model = result.get("Model") or result.get("model") or ""
    year = result.get("ModelYear") or result.get("modelYear") or ""
    trim = result.get("Trim") or result.get("trim") or ""
    engine = result.get("EngineModel") or result.get("engineModel") or ""
    vtype = result.get("VehicleType") or result.get("vehicleType") or ""

    return VinDecodeResponse(
        make=make,
        model=model,
        model_year=str(year),
        trim=trim,
        engine_model=engine,
        vehicle_type=vtype,
        raw=result,
    )


@router.get("/recalls", response_model=RecallsResponse)
async def get_recalls(
    make: str = Query(..., min_length=1),
    model: str = Query(..., min_length=1),
    model_year: int = Query(..., ge=1990, le=2030),
):
    """Get NHTSA recalls for a vehicle by make, model, and year."""
    recalls = nhtsa_service.recalls_by_vehicle(make, model, model_year)
    mapped = [_map_recall(r) for r in recalls]
    return RecallsResponse(
        make=make,
        model=model,
        model_year=model_year,
        count=len(mapped),
        recalls=mapped,
    )


@router.get("/years", response_model=YearsResponse)
async def get_years():
    """Return model years (1996 through current+1) for vehicle dropdown."""
    return YearsResponse(years=nhtsa_service.get_vehicle_years())


@router.get("/makes", response_model=MakesResponse)
async def get_makes(
    vehicle_type: str = Query("car", description="Vehicle type: car, truck, etc."),
):
    """Return makes for a vehicle type (e.g. car) from NHTSA vPIC."""
    raw = nhtsa_service.get_makes_for_vehicle_type(vehicle_type)
    return MakesResponse(makes=[MakeItem(**m) for m in raw])


@router.get("/models", response_model=ModelsResponse)
async def get_models(
    make_id: int = Query(..., description="NHTSA Make ID"),
    model_year: int = Query(..., ge=1995, le=2030, description="Model year"),
):
    """Return models for a make and year from NHTSA vPIC."""
    raw = nhtsa_service.get_models_for_make_id_year(make_id, model_year)
    return ModelsResponse(models=[ModelItem(**m) for m in raw])


@router.get("/selected", response_model=SelectedVehicleResponse)
async def get_selected_vehicle():
    """Return the stored selected vehicle (year, make, model, submodel) for tailored diagnosis."""
    db = get_db_manager()
    row = db.get_selected_vehicle()
    if row is None:
        return SelectedVehicleResponse()
    return SelectedVehicleResponse(
        model_year=row.get("model_year"),
        make=row.get("make") or "",
        model=row.get("model") or "",
        submodel=row.get("submodel") or "",
    )


@router.put("/selected", response_model=SelectedVehicleResponse)
async def set_selected_vehicle(payload: SelectedVehicleResponse):
    """Store the selected vehicle so diagnosis, recalls, and TSBs are tailored to it."""
    db = get_db_manager()
    db.set_selected_vehicle(
        model_year=payload.model_year,
        make=payload.make or "",
        model=payload.model or "",
        submodel=payload.submodel or "",
    )
    return SelectedVehicleResponse(
        model_year=payload.model_year,
        make=payload.make or "",
        model=payload.model or "",
        submodel=payload.submodel or "",
    )


@router.get("/manual-url", response_model=ManualUrlResponse)
async def get_manual_url(
    make: str | None = Query(None, description="Make (e.g. Honda). If omitted, uses selected vehicle."),
    model_year: int | None = Query(None, ge=1982, le=2013, description="Model year. If omitted, uses selected vehicle."),
):
    """
    Return the charm.li (Operation CHARM) service manual URL for this vehicle.
    Open in browser to browse repair manuals (1982–2013). No local hosting required.
    """
    use_make = make
    use_year = model_year
    if use_make is None or use_year is None:
        db = get_db_manager()
        row = db.get_selected_vehicle()
        if row:
            if use_make is None:
                use_make = (row.get("make") or "").strip()
            if use_year is None:
                use_year = row.get("model_year")
    if not use_make:
        return ManualUrlResponse(message="Set a vehicle or pass make= and model_year= to get a manual link.")
    url = charm_li_service.get_manual_url(use_make, use_year)
    if not url:
        return ManualUrlResponse(make=use_make, model_year=use_year, message="Make not found on charm.li.")
    return ManualUrlResponse(url=url, make=use_make, model_year=use_year, message="Open in browser.")
