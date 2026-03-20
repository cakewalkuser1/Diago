"""
Dispatch API: LangGraph multi-agent flow (diagnostics -> parts -> mechanic).
"""

import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_db_manager
from core.dispatch.graph import get_dispatch_graph
from langgraph.types import Command

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class StartDiagnosisRequest(BaseModel):
    """Start the dispatch flow with diagnosis."""
    symptoms: str = ""
    codes: list[str] = Field(default_factory=list)
    behavioral_context: dict[str, Any] = Field(default_factory=dict)
    user_id: Optional[str] = None


class RunDirectRequest(BaseModel):
    """Start dispatch flow without diagnosis — user already knows what's wrong, just needs a mechanic."""
    part_info: str = Field(..., min_length=1, description="Repair/part description (e.g. 'brake pad replacement')")
    user_latitude: Optional[float] = None
    user_longitude: Optional[float] = None
    user_address: Optional[str] = None
    user_id: Optional[str] = None


class ContinueRequest(BaseModel):
    """Continue the flow after an interrupt."""
    thread_id: str
    action: str = Field(..., description="get_parts | part_selected | stock_confirmed | mechanic_selected | mechanic_responded")
    selected_part: Optional[dict[str, Any]] = None
    selected_mechanic_id: Optional[int] = None
    mechanic_accepted: Optional[bool] = None
    user_latitude: Optional[float] = None
    user_longitude: Optional[float] = None
    user_address: Optional[str] = None
    payment_intent_id: Optional[str] = None  # For part_selected: verify payment before proceeding


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state_to_response(state: dict[str, Any]) -> dict[str, Any]:
    """Convert graph state to API response (exclude internal fields)."""
    return {
        "diagnosis_result": state.get("diagnosis_result"),
        "diagnosis_summary": state.get("diagnosis_summary"),
        "suggested_parts": state.get("suggested_parts", []),
        "part_retailers": state.get("part_retailers", []),
        "mechanic_list": state.get("mechanic_list", []),
        "job_id": state.get("job_id"),
        "job_status": state.get("job_status"),
        "current_step": state.get("current_step"),
        "prompt_for_user": state.get("prompt_for_user"),
        "error": state.get("error"),
    }


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/run", response_model=dict)
async def run_dispatch(
    request: StartDiagnosisRequest,
    _db=Depends(get_db_manager),
):
    """
    Start the dispatch flow: run diagnosis, then interrupt before parts.
    Returns thread_id for subsequent continue calls.
    """
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "symptoms": request.symptoms,
        "codes": request.codes,
        "behavioral_context": request.behavioral_context,
        "user_id": request.user_id,
    }

    graph = get_dispatch_graph()
    try:
        result = graph.invoke(initial_state, config=config)
        state = result if isinstance(result, dict) else getattr(result, "__dict__", {})
    except Exception as e:
        logger.exception("Dispatch run failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {
        "thread_id": thread_id,
        **_state_to_response(state),
    }


@router.post("/run-direct", response_model=dict)
async def run_dispatch_direct(
    request: RunDirectRequest,
    _db=Depends(get_db_manager),
):
    """
    Start the dispatch flow without diagnosis. For users who already know what's wrong
    and just need a mechanic. Bypasses diagnosis, parts ordering, and payment.
    """
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    initial_state = {
        "skip_diagnosis": True,
        "part_info": request.part_info.strip(),
        "user_id": request.user_id,
        "user_latitude": request.user_latitude,
        "user_longitude": request.user_longitude,
        "user_address": request.user_address,
    }

    graph = get_dispatch_graph()
    try:
        result = graph.invoke(initial_state, config=config)
        state = result if isinstance(result, dict) else getattr(result, "__dict__", {})
    except Exception as e:
        logger.exception("Dispatch run-direct failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e

    return {
        "thread_id": thread_id,
        **_state_to_response(state),
    }


@router.post("/continue", response_model=dict)
async def continue_dispatch(
    request: ContinueRequest,
    _db=Depends(get_db_manager),
):
    """
    Continue the flow after user/mechanic action.
    - get_parts: resume after diagnosis (no extra input)
    - part_selected: resume with selected_part
    - mechanic_selected: resume with selected_mechanic_id
    - mechanic_responded: resume from interrupt with mechanic_accepted
    """
    config = {"configurable": {"thread_id": request.thread_id}}

    # Build Command for resume (required for all interrupts)
    input_updates = {"thread_id": request.thread_id}
    if request.action == "stock_confirmed":
        input_updates["stock_confirmed"] = True
    elif request.action == "part_selected" and request.selected_part:
        input_updates["selected_part"] = request.selected_part
        # Verify payment: Stripe PaymentIntent must be succeeded (or stub if Stripe not configured)
        payment_confirmed = False
        from core.config import get_settings
        settings = get_settings()
        if request.payment_intent_id == "stub":
            payment_confirmed = not settings.stripe_secret_key  # Stub only when Stripe not configured
        elif request.payment_intent_id:
            from api.payments.stripe_service import get_payment_intent_status
            status = get_payment_intent_status(request.payment_intent_id)
            payment_confirmed = status == "succeeded"
        else:
            payment_confirmed = not settings.stripe_secret_key  # No PI: allow only when Stripe not configured
        if not payment_confirmed:
            raise HTTPException(
                status_code=400,
                detail="Payment not confirmed. Complete payment before proceeding.",
            )
        input_updates["payment_confirmed"] = True
    elif request.action == "mechanic_selected" and request.selected_mechanic_id is not None:
        input_updates["selected_mechanic_id"] = request.selected_mechanic_id
    if request.user_latitude is not None:
        input_updates["user_latitude"] = request.user_latitude
    if request.user_longitude is not None:
        input_updates["user_longitude"] = request.user_longitude
    if request.user_address:
        input_updates["user_address"] = request.user_address

    if request.action == "mechanic_responded":
        if request.mechanic_accepted is None:
            raise HTTPException(status_code=400, detail="mechanic_accepted required for mechanic_responded")
        cmd = Command(resume={"mechanic_accepted": request.mechanic_accepted}, update=input_updates)
    else:
        # Resume from interrupt_before: use Command(resume={}) to continue, update for state
        cmd = Command(resume={}, update=input_updates)

    graph = get_dispatch_graph()
    try:
        result = graph.invoke(cmd, config=config)
    except Exception as e:
        logger.exception("Dispatch continue (%s) failed: %s", request.action, e)
        raise HTTPException(status_code=500, detail=str(e)) from e

    state = result if isinstance(result, dict) else getattr(result, "__dict__", {})
    return {
        "thread_id": request.thread_id,
        **_state_to_response(state),
    }


class CreatePartsOrderRequest(BaseModel):
    """Create a parts order and PaymentIntent for payment."""
    thread_id: str
    part: dict[str, Any]  # { name: str }
    retailer_id: str
    retailer_name: str
    retailer_store_id: str = ""
    user_id: Optional[str] = None


@router.post("/parts-order/create", response_model=dict)
async def create_parts_order(
    request: CreatePartsOrderRequest,
    _db=Depends(get_db_manager),
):
    """
    Create a parts order and Stripe PaymentIntent.
    Returns client_secret for Stripe Elements. If Stripe not configured, returns stub.
    """
    from core.config import get_settings
    from api.payments.stripe_service import create_part_payment_intent

    settings = get_settings()
    part_name = (request.part or {}).get("name", "Part")
    part_description = str(request.part)

    if not settings.stripe_secret_key:
        # Stub: return fake client_secret so frontend can skip to confirm
        return {
            "client_secret": None,
            "payment_intent_id": "stub",
            "amount_cents": settings.stripe_part_price_cents or 4999,
            "stub": True,
        }

    try:
        result = create_part_payment_intent(
            part_description=part_description,
            retailer=request.retailer_name,
            retailer_store_id=request.retailer_store_id or request.retailer_id,
            user_id=request.user_id,
        )
    except RuntimeError as e:
        logger.warning("Stripe not configured: %s", e)
        return {
            "client_secret": None,
            "payment_intent_id": "stub",
            "amount_cents": settings.stripe_part_price_cents or 4999,
            "stub": True,
        }

    db = get_db_manager()
    order_id = db.create_parts_order(
        part_description=part_description,
        retailer=request.retailer_name,
        retailer_store_id=request.retailer_store_id or request.retailer_id,
        amount_cents=result["amount_cents"],
        payment_intent_id=result["payment_intent_id"],
        user_id=request.user_id,
    )
    return {
        "client_secret": result["client_secret"],
        "payment_intent_id": result["payment_intent_id"],
        "amount_cents": result["amount_cents"],
        "order_id": order_id,
        "stub": False,
    }


class MechanicRespondRequest(BaseModel):
    """Mechanic accept/deny a job."""
    accepted: bool


@router.get("/job/{job_id:int}", response_model=dict)
async def get_job(
    job_id: int,
    _db=Depends(get_db_manager),
):
    """Get job details for tracking (customer or mechanic view)."""
    db = get_db_manager()
    cursor = db.connection.execute(
        """SELECT j.id, j.part_info, j.user_latitude, j.user_longitude, j.user_address,
                  j.status, j.assigned_mechanic_id, j.thread_id, j.created_at,
                  j.estimated_arrival_at, j.route_distance_mi, j.route_duration_min,
                  m.name as mechanic_name, m.latitude as mechanic_lat, m.longitude as mechanic_lng
           FROM jobs j
           LEFT JOIN mechanics m ON j.assigned_mechanic_id = m.id
           WHERE j.id = ?""",
        (job_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    return dict(row)


@router.post("/job/{job_id:int}/respond", response_model=dict)
async def mechanic_respond(
    job_id: int,
    request: MechanicRespondRequest,
    _db=Depends(get_db_manager),
):
    """
    Mechanic accepts or denies a job (e.g. from link in SMS/email).
    Job must be in mechanic_pinged status. Resumes the graph with mechanic_accepted.
    """
    db = get_db_manager()
    cursor = db.connection.execute(
        "SELECT id, status, thread_id FROM jobs WHERE id = ?",
        (job_id,),
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    if row["status"] != "mechanic_pinged":
        raise HTTPException(
            status_code=400,
            detail=f"Job not in mechanic_pinged status (current: {row['status']})",
        )
    thread_id = row["thread_id"]
    if not thread_id:
        raise HTTPException(
            status_code=400,
            detail="Job has no thread_id; cannot resume graph",
        )

    config = {"configurable": {"thread_id": thread_id}}
    cmd = Command(resume={"mechanic_accepted": request.accepted})

    graph = get_dispatch_graph()
    try:
        result = graph.invoke(cmd, config=config)
    except Exception as e:
        logger.exception("Mechanic respond (job %s) failed: %s", job_id, e)
        raise HTTPException(status_code=500, detail=str(e)) from e

    state = result if isinstance(result, dict) else getattr(result, "__dict__", {})
    return {
        "thread_id": thread_id,
        "job_id": job_id,
        "accepted": request.accepted,
        **_state_to_response(state),
    }
