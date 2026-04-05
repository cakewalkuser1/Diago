"""
Dispatch graph state for LangGraph multi-agent flow.
Diagnostics -> Parts -> Mechanic discovery -> Ping -> Accept/Deny -> Dispatch.
"""

from typing import Any, Optional, TypedDict


class DispatchState(TypedDict, total=False):
    """Shared state for the dispatch LangGraph."""

    # Intake (for run_diagnosis)
    symptoms: str
    codes: list[str]
    behavioral_context: dict[str, Any]

    # Direct-to-mechanic bypass (skip diagnosis)
    skip_diagnosis: bool
    part_info: str  # User's repair description when skipping diagnosis

    # Diagnosis
    diagnosis_result: Optional[Any]  # DiagnosisResult from core
    diagnosis_summary: Optional[str]
    suggested_parts: list[dict[str, Any]]

    # Parts
    selected_part: Optional[dict[str, Any]]
    part_retailers: list[dict[str, Any]]  # [{id, name, distance, store_id}, ...]
    payment_confirmed: bool
    stock_confirmed: bool

    # Location
    user_latitude: Optional[float]
    user_longitude: Optional[float]
    user_address: Optional[str]

    # Mechanics
    mechanic_list: list[dict[str, Any]]  # [{id, name, distance, availability}, ...]
    selected_mechanic_id: Optional[int]
    mechanic_ping_index: int  # which mechanic we're currently pinging
    mechanic_denied_ids: list[int]

    # Job
    job_id: Optional[int]
    job_status: str  # pending_mechanic, mechanic_pinged, accepted, denied, dispatched, completed
    mechanic_accepted: Optional[bool]  # set when resuming from ping_mechanic interrupt
    thread_id: Optional[str]  # LangGraph thread_id for resuming on mechanic respond

    # Flow control
    user_id: Optional[str]
    current_step: str
    prompt_for_user: str
    error: Optional[str]
    max_mechanic_retries: int
