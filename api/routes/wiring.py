"""
Wiring Diagram API Routes
Search structured wiring diagrams (circuit/connector/pin data) and external references.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from api.deps import get_db_manager

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class WiringPin(BaseModel):
    connector_id: str
    pin_number: str
    wire_color: str = ""
    signal_type: str = ""
    connects_to: str = ""
    typical_value: str = ""
    notes: str = ""


class WiringDiagram(BaseModel):
    id: int
    system: str
    circuit_name: str
    circuit_number: str = ""
    component: str = ""
    description: str = ""
    vehicle_make: str | None = None
    vehicle_model: str | None = None
    year_min: int | None = None
    year_max: int | None = None
    diagram_url: str = ""
    diagram_source: str = ""
    related_codes: str = ""
    related_failure_modes: str = ""
    pins: list[WiringPin] = Field(default_factory=list)


class WiringSearchResponse(BaseModel):
    count: int
    results: list[WiringDiagram]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/search", response_model=WiringSearchResponse)
async def search_wiring_diagrams(
    system: str | None = Query(None, description="System (fuel, ignition, abs, charging, starting, cooling, body, hvac, transmission, other)"),
    component: str | None = Query(None, description="Component name (partial match)"),
    dtc_code: str | None = Query(None, description="Related DTC code (e.g. P0301)"),
    make: str | None = Query(None, description="Vehicle make (partial match)"),
    model: str | None = Query(None, description="Vehicle model (partial match)"),
    year: int | None = Query(None, description="Model year"),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Search wiring diagrams by system, component, related DTC code, or vehicle.
    Results include connector pinout data when available.
    """
    db = get_db_manager()
    rows = db.search_wiring_diagrams(
        system=system,
        component=component,
        dtc_code=dtc_code,
        vehicle_make=make,
        vehicle_model=model,
        model_year=year,
        limit=limit,
    )
    results = [_row_to_diagram(r) for r in rows]
    return WiringSearchResponse(count=len(results), results=results)


@router.get("/{diagram_id}", response_model=WiringDiagram)
async def get_wiring_diagram(diagram_id: int):
    """Fetch a single wiring diagram by ID, including all connector pins."""
    db = get_db_manager()
    row = db.get_wiring_diagram_by_id(diagram_id)
    if not row:
        raise HTTPException(status_code=404, detail="Wiring diagram not found")
    return _row_to_diagram(row)


@router.get("/count")
async def get_wiring_count():
    """Return total number of wiring diagram records."""
    db = get_db_manager()
    return {"count": db.get_wiring_diagram_count()}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_diagram(row: dict) -> WiringDiagram:
    pins = [
        WiringPin(
            connector_id=p.get("connector_id") or "",
            pin_number=p.get("pin_number") or "",
            wire_color=p.get("wire_color") or "",
            signal_type=p.get("signal_type") or "",
            connects_to=p.get("connects_to") or "",
            typical_value=p.get("typical_value") or "",
            notes=p.get("notes") or "",
        )
        for p in (row.get("pins") or [])
    ]
    return WiringDiagram(
        id=row["id"],
        system=row.get("system") or "",
        circuit_name=row.get("circuit_name") or "",
        circuit_number=row.get("circuit_number") or "",
        component=row.get("component") or "",
        description=row.get("description") or "",
        vehicle_make=row.get("vehicle_make"),
        vehicle_model=row.get("vehicle_model"),
        year_min=row.get("year_min"),
        year_max=row.get("year_max"),
        diagram_url=row.get("diagram_url") or "",
        diagram_source=row.get("diagram_source") or "",
        related_codes=row.get("related_codes") or "",
        related_failure_modes=row.get("related_failure_modes") or "",
        pins=pins,
    )
