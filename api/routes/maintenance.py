"""
Maintenance tracking API: vehicle service history and due-date alerts.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field

from api.deps import get_db_manager

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_user_id(x_user_id: Optional[str] = Header(None)) -> str:
    return x_user_id or "anon"


class CreateMaintenanceRecord(BaseModel):
    """Create a maintenance record."""
    vehicle_vin: Optional[str] = None
    vehicle_year: Optional[int] = None
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    service_type: str = Field(..., min_length=1)
    mileage: Optional[int] = None
    performed_at: Optional[str] = None
    next_due_mileage: Optional[int] = None
    next_due_date: Optional[str] = None
    notes: Optional[str] = None


@router.get("/records", response_model=list)
async def list_maintenance_records(
    user_id: str = Depends(_get_user_id),
    vehicle_vin: Optional[str] = None,
    limit: int = 50,
    db=Depends(get_db_manager),
):
    """List maintenance records for the user, optionally filtered by VIN."""
    cursor = db.connection.execute(
        """SELECT id, vehicle_vin, vehicle_year, vehicle_make, vehicle_model,
                  service_type, mileage, performed_at, next_due_mileage, next_due_date, notes, created_at
           FROM maintenance_records
           WHERE user_id = ?
           ORDER BY COALESCE(performed_at, '') DESC, created_at DESC
           LIMIT ?""",
        (user_id, limit),
    )
    rows = cursor.fetchall()
    if vehicle_vin:
        rows = [r for r in rows if (r["vehicle_vin"] or "").strip() == vehicle_vin.strip()]
    return [dict(r) for r in rows]


@router.post("/records", response_model=dict)
async def create_maintenance_record(
    request: CreateMaintenanceRecord,
    user_id: str = Depends(_get_user_id),
    db=Depends(get_db_manager),
):
    """Create a maintenance record."""
    cursor = db.connection.execute(
        """INSERT INTO maintenance_records
           (user_id, vehicle_vin, vehicle_year, vehicle_make, vehicle_model,
            service_type, mileage, performed_at, next_due_mileage, next_due_date, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            user_id,
            (request.vehicle_vin or "").strip() or None,
            request.vehicle_year,
            request.vehicle_make,
            request.vehicle_model,
            request.service_type,
            request.mileage,
            request.performed_at,
            request.next_due_mileage,
            request.next_due_date,
            request.notes,
        ),
    )
    db.connection.commit()
    return {"id": cursor.lastrowid, "ok": True}


@router.get("/schedules", response_model=list)
async def list_maintenance_schedules(db=Depends(get_db_manager)):
    """List common maintenance schedules (oil change, tire rotation, etc.)."""
    cursor = db.connection.execute(
        "SELECT id, service_type, interval_miles, interval_months, description FROM maintenance_schedules"
    )
    return [dict(r) for r in cursor.fetchall()]


@router.get("/due", response_model=list)
async def get_due_maintenance(
    user_id: str = Depends(_get_user_id),
    current_mileage: Optional[int] = None,
    db=Depends(get_db_manager),
):
    """
    Get maintenance items due soon based on records and schedules.
    Compares next_due_mileage/next_due_date with current mileage/date.
    """
    cursor = db.connection.execute(
        """SELECT id, vehicle_vin, vehicle_year, vehicle_make, vehicle_model,
                  service_type, mileage, next_due_mileage, next_due_date
           FROM maintenance_records
           WHERE user_id = ? AND (next_due_mileage IS NOT NULL OR next_due_date IS NOT NULL)""",
        (user_id,),
    )
    rows = cursor.fetchall()
    due = []
    today = datetime.utcnow().date().isoformat()
    for r in rows:
        overdue = False
        if r["next_due_mileage"] is not None and current_mileage is not None:
            if current_mileage >= r["next_due_mileage"]:
                overdue = True
        if r["next_due_date"] and r["next_due_date"] <= today:
            overdue = True
        if overdue:
            due.append(dict(r))
    return due
