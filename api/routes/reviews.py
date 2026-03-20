"""
Reviews API: post-job ratings and comments.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field

from api.deps import get_db_manager

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_user_id(x_user_id: Optional[str] = Header(None)) -> str:
    return x_user_id or "anon"


class CreateReviewRequest(BaseModel):
    """Create a review after job completion."""
    job_id: int
    reviewer_role: str = Field(..., pattern="^(customer|mechanic)$")
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


@router.post("/", response_model=dict)
async def create_review(
    request: CreateReviewRequest,
    user_id: str = Depends(_get_user_id),
    db=Depends(get_db_manager),
):
    """
    Submit a review for a completed job.
    customer reviews mechanic; mechanic reviews customer.
    One review per (job_id, reviewer_role).
    """
    cursor = db.connection.execute(
        "SELECT id, status, assigned_mechanic_id, user_id FROM jobs WHERE id = ?",
        (request.job_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    if row["status"] != "completed" and row["status"] != "accepted":
        raise HTTPException(status_code=400, detail="Job must be completed to review")
    reviewee_id = str(row["assigned_mechanic_id"]) if request.reviewer_role == "customer" else str(row["user_id"] or "anon")
    try:
        db.connection.execute(
            """INSERT INTO reviews (job_id, reviewer_id, reviewee_id, reviewer_role, rating, comment)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (request.job_id, user_id, reviewee_id, request.reviewer_role, request.rating, request.comment or ""),
        )
        db.connection.commit()
    except Exception as e:
        if "UNIQUE" in str(e) or "unique" in str(e).lower():
            raise HTTPException(status_code=400, detail="Already reviewed this job")
        raise
    # Update mechanic rating if customer reviewed
    if request.reviewer_role == "customer" and row["assigned_mechanic_id"]:
        cursor = db.connection.execute(
            "SELECT AVG(rating) as avg_rating, COUNT(*) as cnt FROM reviews WHERE reviewee_id = ? AND reviewer_role = 'customer'",
            (str(row["assigned_mechanic_id"]),),
        )
        r = cursor.fetchone()
        if r and r["cnt"] > 0:
            db.connection.execute(
                "UPDATE mechanics SET rating = ?, total_jobs = ? WHERE id = ?",
                (r["avg_rating"], r["cnt"], row["assigned_mechanic_id"]),
            )
            db.connection.commit()
    return {"ok": True, "message": "Review submitted"}


@router.get("/mechanic/{mechanic_id:int}", response_model=list)
async def get_mechanic_reviews(
    mechanic_id: int,
    limit: int = 10,
    db=Depends(get_db_manager),
):
    """Get reviews for a mechanic (by reviewee_id = mechanic_id)."""
    cursor = db.connection.execute(
        """SELECT r.rating, r.comment, r.created_at, r.reviewer_role
           FROM reviews r
           WHERE r.reviewee_id = ? AND r.reviewer_role = 'customer'
           ORDER BY r.created_at DESC
           LIMIT ?""",
        (str(mechanic_id), limit),
    )
    return [dict(row) for row in cursor.fetchall()]
