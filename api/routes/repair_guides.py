"""
Repair guides API (CarDiagn + charm.li).
Search and for-diagnosis only; no separate public API for charm.li.
"""

from fastapi import APIRouter, Query

from api.services import repair_guides as repair_guides_service

router = APIRouter()


@router.get("/search")
async def search_repair_guides(
    q: str | None = Query(None, description="Free-text search"),
    make: str | None = Query(None),
    model: str | None = Query(None),
    year: int | None = Query(None, ge=1980, le=2030),
    source: str | None = Query(None, description="cardiagn or charm_li"),
    limit: int = Query(10, ge=1, le=50),
):
    """Search repair guides by query and/or vehicle."""
    return repair_guides_service.search(q=q, make=make, model=model, year=year, source=source, limit=limit)


@router.get("/for-diagnosis")
async def repair_guides_for_diagnosis(
    q: str | None = Query(None, description="Symptoms or diagnosis summary"),
    make: str | None = Query(None),
    model: str | None = Query(None),
    year: int | None = Query(None, ge=1980, le=2030),
    limit: int = Query(3, ge=1, le=10),
):
    """Return a few relevant repair guides for the current diagnosis context."""
    return repair_guides_service.for_diagnosis(
        symptoms_summary=q,
        make=make,
        model=model,
        year=year,
        limit=limit,
    )
