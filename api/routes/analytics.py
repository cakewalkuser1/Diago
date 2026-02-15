"""
Analytics API Routes (Enterprise)
Shop analytics and diagnostics overview.
"""

import logging

from fastapi import APIRouter, Depends

from api.deps import get_db_manager

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def get_analytics():
    """Return shop analytics: total diagnoses, repair logs, etc."""
    db = get_db_manager()
    return db.get_analytics()
