"""
LangGraph dispatch flow: Diagnostics -> Parts -> Mechanic discovery -> Ping -> Dispatch.
"""

import logging
from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt

from core.dispatch.state import DispatchState

logger = logging.getLogger(__name__)

# Parts by mechanical class (mirrors frontend PARTS_BY_CLASS)
PARTS_BY_CLASS: dict[str, list[str]] = {
    "rolling_element_bearing": ["Wheel bearing", "Idler pulley", "Alternator bearing", "Water pump bearing", "A/C compressor clutch"],
    "gear_mesh_drivetrain": ["Differential gears", "Transmission gears", "Transfer case", "CV axle", "Drive shaft support bearing"],
    "belt_drive_friction": ["Serpentine belt", "Belt tensioner", "Idler pulley", "A/C belt", "Alternator belt"],
    "hydraulic_flow_cavitation": ["Power steering pump", "Power steering fluid", "Transmission cooler", "Hydraulic pump"],
    "electrical_interference": ["Alternator", "Fuel pump", "Ignition coil", "Spark plug wires", "Ground strap"],
    "combustion_impulse": ["Spark plugs", "Ignition coils", "Fuel injectors", "Knock sensor", "Timing chain/belt"],
    "structural_resonance": ["Motor mount", "Transmission mount", "Exhaust hanger", "Heat shield", "Suspension bushing"],
    "unknown": ["Inspect symptom area", "Check related sensors", "Review codes"],
}

# Fallback when parts API returns nothing
MOCK_RETAILERS = [
    {"id": "az1", "name": "AutoZone", "distance_mi": 2.1, "store_id": "store_az_1"},
    {"id": "napa1", "name": "NAPA", "distance_mi": 3.0, "store_id": "store_napa_1"},
    {"id": "oreilly1", "name": "O'Reilly", "distance_mi": 2.5, "store_id": "store_oreilly_1"},
]


def _get_part_retailers(part_name: str, user_lat: float | None, user_lng: float | None) -> list[dict]:
    """Get retailers from parts API or fallback to mock."""
    try:
        from api.services.parts_pricing import get_parts_from_all_retailers
        retailers = get_parts_from_all_retailers(part_name, lat=user_lat, lng=user_lng)
        if retailers:
            return retailers
    except Exception as e:
        logger.debug("Parts pricing unavailable: %s", e)
    return MOCK_RETAILERS.copy()

def _should_skip_diagnosis(state: DispatchState) -> bool:
    """True if user wants to skip diagnosis and go straight to mechanic."""
    return bool(state.get("skip_diagnosis") and state.get("part_info"))


def direct_to_mechanic_setup_node(state: DispatchState) -> dict:
    """Bypass diagnosis: set up state from user's repair description and go to find mechanics."""
    part_info = (state.get("part_info") or "").strip() or "Repair as described"
    retailers = _get_part_retailers(part_info, state.get("user_latitude"), state.get("user_longitude"))
    return {
        "suggested_parts": [{"name": part_info}],
        "selected_part": {"name": part_info},
        "part_retailers": retailers,
        "stock_confirmed": True,
        "payment_confirmed": True,
        "current_step": "awaiting_find_mechanics",
        "prompt_for_user": "Share your location to find nearby mechanics, or we'll show all available.",
    }


def run_diagnosis_node(state: DispatchState) -> dict:
    """Run the diagnostic pipeline and store result in state."""
    from api.deps import get_db_manager
    from core.api import run_diagnosis
    from core.feature_extraction import BehavioralContext

    symptoms = state.get("symptoms", "") or ""
    codes = state.get("codes", []) or []
    ctx_dict = state.get("behavioral_context") or {}
    ctx = BehavioralContext(**ctx_dict) if ctx_dict else None

    db = get_db_manager()
    result = run_diagnosis(
        audio=None,
        sr=44100,
        codes=codes,
        symptoms=symptoms,
        context=ctx,
        db_manager=db,
    )

    # Serialize for state (DiagnosisResult has many fields)
    top_class = result.top_class
    suggested = PARTS_BY_CLASS.get(top_class, PARTS_BY_CLASS["unknown"])
    summary = result.llm_narrative or f"Top mechanical class: {top_class}. Confidence: {result.confidence}."

    return {
        "diagnosis_result": _serialize_diagnosis(result),
        "diagnosis_summary": summary,
        "suggested_parts": [{"name": p} for p in suggested],
        "current_step": "diagnosis_complete",
        "prompt_for_user": "Here's what we found. Would you like to get parts?",
    }


def _serialize_diagnosis(result) -> dict:
    """Serialize DiagnosisResult for JSON/state (convert numpy types)."""
    def _to_native(obj):
        if hasattr(obj, "item"):  # numpy scalar
            return obj.item()
        if isinstance(obj, dict):
            return {k: _to_native(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_to_native(v) for v in obj]
        return obj

    scores = _to_native(getattr(result, "class_scores", {}))
    return {
        "top_class": result.top_class,
        "confidence": result.confidence,
        "is_ambiguous": result.is_ambiguous,
        "class_scores": scores,
        "llm_narrative": result.llm_narrative,
    }


def summarize_diagnosis_node(state: DispatchState) -> dict:
    """Summarize diagnosis for user (stub; diagnosis node already sets summary)."""
    return {
        "current_step": "awaiting_get_parts",
        "prompt_for_user": "Here's what we found. Would you like to get parts?",
    }


def suggest_parts_node(state: DispatchState) -> dict:
    """Suggest parts and local retailers. Interrupt for user to pick part."""
    suggested = state.get("suggested_parts", [])
    part_name = suggested[0]["name"] if suggested else "Part"
    retailers = _get_part_retailers(part_name, state.get("user_latitude"), state.get("user_longitude"))
    return {
        "part_retailers": retailers,
        "suggested_parts": suggested,
        "current_step": "awaiting_part_selection",
        "prompt_for_user": "Select a part and retailer, then complete payment.",
    }


def check_stock_node(state: DispatchState) -> dict:
    """Check part stock. Manual confirmation: user verifies on retailer site."""
    return {
        "current_step": "awaiting_stock_confirmation",
        "prompt_for_user": "Please confirm the part is in stock at the retailer (check their website or call).",
    }


def stock_confirmed_node(state: DispatchState) -> dict:
    """User confirmed stock; proceed to find mechanics."""
    return {
        "stock_confirmed": True,
        "current_step": "stock_confirmed",
        "prompt_for_user": "Part confirmed in stock. Finding nearby mechanics…",
    }


def find_mechanics_node(state: DispatchState) -> dict:
    """Find mechanics in vicinity from DB (Haversine). Fallback: all available if no location."""
    from api.deps import get_db_manager

    db = get_db_manager()
    user_lat = state.get("user_latitude")
    user_lng = state.get("user_longitude")
    mechanics = db.get_mechanics_by_vicinity(
        user_lat=user_lat,
        user_lng=user_lng,
        radius_mi=25.0,
        limit=10,
    )
    return {
        "mechanic_list": mechanics,
        "mechanic_ping_index": 0,
        "mechanic_denied_ids": [],
        "current_step": "awaiting_mechanic_selection",
        "prompt_for_user": "Select a mechanic to send the job to.",
    }


def ping_mechanic_node(state: DispatchState) -> dict:
    """Ping the selected mechanic. Interrupt for mechanic accept/deny."""
    from api.deps import get_db_manager

    mechanic_list = state.get("mechanic_list", [])
    selected_id = state.get("selected_mechanic_id")
    if not mechanic_list or selected_id is None:
        return {"error": "No mechanic selected", "current_step": "error"}

    mechanic = next((m for m in mechanic_list if m.get("id") == selected_id), None)
    if not mechanic:
        return {"error": "Mechanic not found", "current_step": "error"}

    db = get_db_manager()
    thread_id = state.get("thread_id")
    job_id = state.get("job_id")
    if job_id:
        # Update existing job with next mechanic
        db.connection.execute(
            "UPDATE jobs SET assigned_mechanic_id = ?, status = 'mechanic_pinged', thread_id = COALESCE(?, thread_id), updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (selected_id, thread_id, job_id),
        )
        db.connection.commit()
    else:
        # Create new job (persist thread_id for mechanic respond endpoint)
        cursor = db.connection.execute(
            """
            INSERT INTO jobs (user_id, part_info, user_latitude, user_longitude, status, assigned_mechanic_id, thread_id)
            VALUES (?, ?, ?, ?, 'mechanic_pinged', ?, ?)
            """,
            (
                state.get("user_id"),
                str(state.get("selected_part", {})),
                state.get("user_latitude"),
                state.get("user_longitude"),
                selected_id,
                thread_id,
            ),
        )
        job_id = cursor.lastrowid
        db.connection.commit()

    # Interrupt: wait for mechanic to accept/deny. On resume, response has mechanic_accepted.
    response = interrupt({"job_id": job_id, "mechanic_name": mechanic.get("name", "Mechanic")})
    mechanic_accepted = response.get("mechanic_accepted") if isinstance(response, dict) else None

    return {
        "job_id": job_id,
        "job_status": "mechanic_pinged",
        "mechanic_accepted": mechanic_accepted,
        "current_step": "awaiting_mechanic_response",
        "prompt_for_user": f"Job sent to {mechanic.get('name')}. Waiting for response.",
    }


def on_accept_node(state: DispatchState) -> dict:
    """Mechanic accepted: dispatch. Compute ETA and update job with tracking fields."""
    from datetime import datetime, timedelta

    job_id = state.get("job_id")
    if job_id:
        from api.deps import get_db_manager
        from core.dispatch.routing import get_route_eta

        db = get_db_manager()
        cursor = db.connection.execute(
            """SELECT j.user_latitude, j.user_longitude, m.latitude as m_lat, m.longitude as m_lng
               FROM jobs j
               JOIN mechanics m ON j.assigned_mechanic_id = m.id
               WHERE j.id = ?""",
            (job_id,),
        )
        row = cursor.fetchone()
        route_distance_mi = None
        route_duration_min = None
        estimated_arrival_at = None
        if row and row["user_latitude"] and row["user_longitude"] and row["m_lat"] and row["m_lng"]:
            route = get_route_eta(
                row["m_lat"], row["m_lng"],
                row["user_latitude"], row["user_longitude"],
            )
            route_distance_mi = route.distance_mi
            route_duration_min = route.duration_min
            eta = datetime.utcnow() + timedelta(minutes=route.duration_min)
            estimated_arrival_at = eta.strftime("%Y-%m-%dT%H:%M:%SZ")

        db.connection.execute(
            """UPDATE jobs SET status = 'accepted', mechanic_accepted_at = CURRENT_TIMESTAMP,
               route_distance_mi = ?, route_duration_min = ?, estimated_arrival_at = ?,
               updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
            (route_distance_mi, route_duration_min, estimated_arrival_at, job_id),
        )
        db.connection.commit()

    return {
        "job_status": "accepted",
        "current_step": "dispatched",
        "prompt_for_user": "Mechanic accepted! They will pick up the part and head to you. Track their arrival on the map.",
    }


def on_deny_next_node(state: DispatchState) -> dict:
    """Mechanic denied: try next mechanic or give up."""
    mechanic_list = state.get("mechanic_list", [])
    denied_ids = state.get("mechanic_denied_ids", []) or []
    ping_index = state.get("mechanic_ping_index", 0)
    selected_id = state.get("selected_mechanic_id")
    max_retries = state.get("max_mechanic_retries", 5)

    if selected_id is not None:
        denied_ids = list(denied_ids) + [selected_id]

    available = [m for m in mechanic_list if m.get("id") not in denied_ids]
    if not available or len(denied_ids) >= max_retries:
        return {
            "current_step": "no_mechanic_accepted",
            "prompt_for_user": "No mechanic accepted. Try again later or expand your search radius.",
        }
    next_mechanic = available[0]
    return {
        "mechanic_denied_ids": denied_ids,
        "selected_mechanic_id": next_mechanic["id"],
        "mechanic_ping_index": ping_index + 1,
        "current_step": "pinging_next",
        "prompt_for_user": f"Trying next mechanic: {next_mechanic.get('name')}.",
    }


def route_after_ping(state: DispatchState) -> Literal["on_accept", "on_deny_next", "find_mechanics"]:
    """Route based on mechanic response (accepted vs denied)."""
    # When resuming from interrupt, the state will have mechanic_accepted from the Command
    mechanic_accepted = state.get("mechanic_accepted")
    if mechanic_accepted is True:
        return "on_accept"
    if mechanic_accepted is False:
        return "on_deny_next"
    # Default: shouldn't happen
    return "on_deny_next"


def _route_start(state: DispatchState) -> Literal["direct_setup", "run_diagnosis"]:
    """Route from START: direct to mechanic or full diagnosis flow."""
    return "direct_setup" if _should_skip_diagnosis(state) else "run_diagnosis"


def build_dispatch_graph():
    """Build and compile the dispatch LangGraph."""
    builder = StateGraph(DispatchState)

    builder.add_node("direct_setup", direct_to_mechanic_setup_node)
    builder.add_node("run_diagnosis", run_diagnosis_node)
    builder.add_node("summarize_diagnosis", summarize_diagnosis_node)
    builder.add_node("suggest_parts", suggest_parts_node)
    builder.add_node("check_stock", check_stock_node)
    builder.add_node("stock_confirmed", stock_confirmed_node)
    builder.add_node("find_mechanics", find_mechanics_node)
    builder.add_node("ping_mechanic", ping_mechanic_node)
    builder.add_node("on_accept", on_accept_node)
    builder.add_node("on_deny_next", on_deny_next_node)

    builder.add_conditional_edges(START, _route_start, {"direct_setup": "direct_setup", "run_diagnosis": "run_diagnosis"})
    builder.add_edge("direct_setup", "find_mechanics")
    builder.add_edge("run_diagnosis", "summarize_diagnosis")
    builder.add_edge("summarize_diagnosis", "suggest_parts")
    builder.add_edge("suggest_parts", "check_stock")
    builder.add_edge("check_stock", "stock_confirmed")
    builder.add_edge("stock_confirmed", "find_mechanics")
    builder.add_edge("find_mechanics", "ping_mechanic")
    builder.add_conditional_edges("ping_mechanic", route_after_ping, {"on_accept": "on_accept", "on_deny_next": "on_deny_next"})
    builder.add_edge("on_accept", END)
    builder.add_edge("on_deny_next", "ping_mechanic")  # Loop back to ping next mechanic

    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer, interrupt_before=["suggest_parts", "stock_confirmed", "find_mechanics", "ping_mechanic"])


# Compiled graph instance (lazy init)
_compiled_graph = None


def get_dispatch_graph():
    """Get the compiled dispatch graph (singleton)."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_dispatch_graph()
    return _compiled_graph
