"""
Repairs API Routes (Enterprise)
Endpoints for repair logging and VIN-based history.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from api.deps import get_db_manager

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class CreateRepairRequest(BaseModel):
    """Request to create a repair log."""
    session_id: Optional[int] = None
    vin: Optional[str] = None
    repair_description: str = Field(..., min_length=1)
    parts_used: str = ""
    outcome: str = ""


class RepairLogResponse(BaseModel):
    """Repair log entry."""
    id: int
    session_id: Optional[int]
    vin: Optional[str]
    repair_description: str
    parts_used: str
    outcome: str
    created_at: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/", response_model=dict)
async def create_repair(request: CreateRepairRequest):
    """Create a new repair log entry."""
    db = get_db_manager()
    log_id = db.create_repair_log(
        session_id=request.session_id,
        vin=request.vin,
        repair_description=request.repair_description,
        parts_used=request.parts_used or "",
        outcome=request.outcome or "",
    )
    return {"id": log_id}


@router.get("/", response_model=list[RepairLogResponse])
async def list_repairs(
    vin: Optional[str] = Query(None, description="Filter by VIN"),
    session_id: Optional[int] = Query(None, description="Filter by session ID"),
    limit: int = Query(50, ge=1, le=200),
):
    """List repair logs, optionally filtered by VIN or session."""
    db = get_db_manager()
    logs = db.list_repair_logs(vin=vin, session_id=session_id, limit=limit)
    return [
        RepairLogResponse(
            id=row["id"],
            session_id=row["session_id"],
            vin=row["vin"],
            repair_description=row["repair_description"],
            parts_used=row["parts_used"] or "",
            outcome=row["outcome"] or "",
            created_at=row["created_at"] or "",
        )
        for row in logs
    ]
