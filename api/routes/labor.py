"""
Labor Times API Routes
Look up flat-rate labor hours for repair operations, optionally filtered by vehicle.
"""

import logging

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from api.deps import get_db_manager
from api.services.motor_daas import get_labor_times as stub_labor_times, get_upfront_estimate

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class LaborTimeItem(BaseModel):
    operation_key: str
    operation_name: str
    labor_hours: float
    labor_hours_max: float | None = None
    vehicle_make: str | None = None
    vehicle_model: str | None = None
    year_min: int | None = None
    year_max: int | None = None
    skill_level: str = "intermediate"
    notes: str = ""
    related_codes: str = ""
    mechanical_class: str = ""


class LaborSearchResponse(BaseModel):
    count: int
    results: list[LaborTimeItem]


class EstimateResponse(BaseModel):
    operation: str
    labor_hours: float
    labor_hours_max: float | None = None
    labor_rate_per_hour: float
    labor_total: float
    parts_total: float
    grand_total: float
    operations: list[dict] = Field(default_factory=list)
    parts: list[dict] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/search", response_model=LaborSearchResponse)
async def search_labor_times(
    operation: str = Query(..., description="Operation name or key (e.g. 'brake_pad_front', 'spark plug')"),
    make: str | None = Query(None, description="Vehicle make"),
    model: str | None = Query(None, description="Vehicle model"),
    year: int | None = Query(None, description="Model year"),
):
    """
    Look up flat-rate labor hours for a repair operation.
    Returns the most-specific match first (make+model+year > generic).
    Falls back to the stub database if the local table is empty.
    """
    db = get_db_manager()
    rows = db.get_labor_times(
        operation_key=operation,
        vehicle_make=make,
        vehicle_model=model,
        model_year=year,
    )

    if rows:
        results = [_row_to_item(r) for r in rows]
    else:
        # Fallback: stub data
        stub_results = stub_labor_times(year or 0, make or "", model or "", operation)
        results = [
            LaborTimeItem(
                operation_key=operation,
                operation_name=lt.operation,
                labor_hours=lt.hours,
                labor_hours_max=lt.hours_max,
                skill_level=lt.skill_level,
                notes=lt.notes,
            )
            for lt in stub_results
        ]

    return LaborSearchResponse(count=len(results), results=results)


@router.get("/estimate", response_model=EstimateResponse)
async def get_repair_estimate(
    operation: str = Query(..., description="Operation name or key"),
    make: str | None = Query(None),
    model: str | None = Query(None),
    year: int | None = Query(None),
    labor_rate: float = Query(150.0, ge=50.0, le=500.0, description="Shop labor rate per hour (USD)"),
):
    """
    Return a full repair estimate (labor + parts) for a given operation.
    Labor rate defaults to $150/hr; override with the labor_rate parameter.
    """
    year_i = year or 0
    make_s = make or ""
    model_s = model or ""

    estimate = get_upfront_estimate(
        year=year_i,
        make=make_s,
        model=model_s,
        part_info=operation,
        labor_rate_cents_per_hour=int(labor_rate * 100),
    )

    return EstimateResponse(
        operation=operation,
        labor_hours=estimate["labor_hours"],
        labor_hours_max=estimate.get("labor_hours_max"),
        labor_rate_per_hour=labor_rate,
        labor_total=estimate["labor_cents"] / 100,
        parts_total=estimate["parts_cents"] / 100,
        grand_total=estimate["total_cents"] / 100,
        operations=estimate.get("operations", []),
        parts=estimate.get("parts", []),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_item(row: dict) -> LaborTimeItem:
    return LaborTimeItem(
        operation_key=row.get("operation_key") or "",
        operation_name=row.get("operation_name") or "",
        labor_hours=float(row.get("labor_hours") or 1.0),
        labor_hours_max=row.get("labor_hours_max"),
        vehicle_make=row.get("vehicle_make"),
        vehicle_model=row.get("vehicle_model"),
        year_min=row.get("year_min"),
        year_max=row.get("year_max"),
        skill_level=row.get("skill_level") or "intermediate",
        notes=row.get("notes") or "",
        related_codes=row.get("related_codes") or "",
        mechanical_class=row.get("mechanical_class") or "",
    )
