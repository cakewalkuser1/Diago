"""
Diagnosis API Routes
Endpoints for running diagnostic analysis (audio + text).
"""

import base64
import io
import logging
from typing import Optional

import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from api.deps import get_db_manager
from api.middleware.auth import get_optional_user
from api.middleware.rate_limit import (
    check_diagnosis_rate_limit,
    increment_diagnosis_count,
)
from core.api import run_diagnosis, export_report
from core.feature_extraction import BehavioralContext
from core.models import VehicleIntake, FuelTrimIntake

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class BehavioralContextRequest(BaseModel):
    """Behavioral context from the user."""
    rpm_dependency: bool = False
    speed_dependency: bool = False
    load_dependency: bool = False
    cold_only: bool = False
    occurs_at_idle: bool = False
    mechanical_localization: bool = False
    noise_character: str = "unknown"
    perceived_frequency: str = "unknown"
    intermittent: bool = False
    issue_duration: str = "unknown"
    vehicle_type: str = "unknown"
    mileage_range: str = "unknown"
    recent_maintenance: str = "unknown"


class FuelTrimRequest(BaseModel):
    """Optional fuel trim data (STFT/LTFT %)."""
    stft: Optional[float] = None
    ltft: Optional[float] = None


class TextDiagnosisRequest(BaseModel):
    """Request for text-only diagnosis."""
    symptoms: str = ""
    codes: list[str] = Field(default_factory=list)
    context: BehavioralContextRequest = Field(default_factory=BehavioralContextRequest)
    plain_english: bool = False
    fuel_trims: Optional[FuelTrimRequest] = None


class ClassScore(BaseModel):
    """A single mechanical class score."""
    class_name: str
    display_name: str
    score: float
    penalty: float


class ConfirmTest(BaseModel):
    """A suggested confirm test for a failure mode."""
    test: str
    tool: str
    expected: str


class RankedFailureMode(BaseModel):
    """A ranked failure mode from the pattern engine (master-tech)."""
    failure_id: str
    display_name: str
    description: str
    score: float
    confirm_tests: list[dict]
    matched_conditions: list[str]
    ruled_out_disqualifiers: list[str]


class DiagnosisResponse(BaseModel):
    """Response from the diagnosis endpoint."""
    top_class: str
    top_class_display: str
    confidence: str
    is_ambiguous: bool
    class_scores: list[ClassScore]
    fingerprint_count: int
    llm_narrative: Optional[str] = None
    report_text: str
    ranked_failure_modes: list[RankedFailureMode] = []


class ReportRequest(BaseModel):
    """Request to generate a report from a previous diagnosis."""
    top_class: str
    confidence: str
    is_ambiguous: bool
    class_scores: dict[str, float]
    penalties_applied: dict[str, float]
    features: dict
    fingerprint_count: int = 0


class ConfirmTestRequest(BaseModel):
    """Request to apply a confirm test result and re-rank failure modes."""
    ranked_failure_modes: list[RankedFailureMode]
    test_id: str
    result: str  # "pass" or "fail"


class ConfirmTestResponse(BaseModel):
    """Updated ranked failure modes after applying confirm test."""
    ranked_failure_modes: list[RankedFailureMode]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

def _client_ip(request: Request) -> str:
    """Get client IP for rate limiting (anonymous key)."""
    if request.client:
        return request.client.host or "unknown"
    return "unknown"


@router.post("/text", response_model=DiagnosisResponse)
async def diagnose_text(
    request: TextDiagnosisRequest,
    req: Request,
    user=Depends(get_optional_user),
):
    """
    Run text-only diagnosis from symptoms, codes, and behavioral context.
    No audio required. Rate-limited by tier (optional auth).
    """
    from core.diagnostic_engine import CLASS_DISPLAY_NAMES

    client_ip = _client_ip(req)
    check_diagnosis_rate_limit(user, client_ip)

    db = get_db_manager()

    # Build vehicle intake from selected vehicle (optional; backward compatible)
    vehicle_intake = None
    selected = db.get_selected_vehicle()
    if selected:
        vehicle_intake = VehicleIntake(
            year=selected.get("model_year"),
            make=selected.get("make", "") or "",
            model=selected.get("model", "") or "",
            engine=selected.get("submodel", "") or "",
        )

    ctx = BehavioralContext(
        rpm_dependency=request.context.rpm_dependency,
        speed_dependency=request.context.speed_dependency,
        load_dependency=request.context.load_dependency,
        cold_only=request.context.cold_only,
        occurs_at_idle=request.context.occurs_at_idle,
        mechanical_localization=request.context.mechanical_localization,
        noise_character=request.context.noise_character,
        perceived_frequency=request.context.perceived_frequency,
        intermittent=request.context.intermittent,
        issue_duration=request.context.issue_duration,
        vehicle_type=request.context.vehicle_type,
        mileage_range=request.context.mileage_range,
        recent_maintenance=request.context.recent_maintenance,
    )

    fuel_intake = None
    if request.fuel_trims and (request.fuel_trims.stft is not None or request.fuel_trims.ltft is not None):
        fuel_intake = FuelTrimIntake(
            stft=request.fuel_trims.stft,
            ltft=request.fuel_trims.ltft,
        )

    try:
        result = run_diagnosis(
            audio=None,
            sr=44100,
            codes=request.codes,
            symptoms=request.symptoms,
            context=ctx,
            db_manager=db,
            vehicle_intake=vehicle_intake,
            plain_english=request.plain_english,
            fuel_trims=fuel_intake,
        )
    except Exception as e:
        logger.error("Text diagnosis failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    increment_diagnosis_count(user, client_ip)

    report_text = export_report(result)

    ranked = getattr(result, "ranked_failure_modes", None) or []
    return DiagnosisResponse(
        top_class=result.top_class,
        top_class_display=CLASS_DISPLAY_NAMES.get(result.top_class, result.top_class),
        confidence=result.confidence,
        is_ambiguous=result.is_ambiguous,
        class_scores=[
            ClassScore(
                class_name=cls,
                display_name=CLASS_DISPLAY_NAMES.get(cls, cls),
                score=score,
                penalty=result.penalties_applied.get(cls, 0.0),
            )
            for cls, score in sorted(
                result.class_scores.items(), key=lambda x: x[1], reverse=True
            )
        ],
        fingerprint_count=result.fingerprint_count,
        llm_narrative=result.llm_narrative,
        report_text=report_text,
        ranked_failure_modes=[
            RankedFailureMode(
                failure_id=m.failure_id,
                display_name=m.display_name,
                description=m.description,
                score=m.score,
                confirm_tests=getattr(m, "confirm_tests", []) or [],
                matched_conditions=getattr(m, "matched_conditions", []) or [],
                ruled_out_disqualifiers=getattr(m, "ruled_out_disqualifiers", []) or [],
            )
            for m in ranked
        ],
    )


@router.post("/audio", response_model=DiagnosisResponse)
async def diagnose_audio(
    req: Request,
    user=Depends(get_optional_user),
    audio_file: UploadFile = File(...),
    symptoms: str = Form(""),
    codes: str = Form(""),
    plain_english: bool = Form(False),
):
    """
    Run audio diagnosis by uploading an audio file.
    Optionally include symptoms and trouble codes. Rate-limited by tier (optional auth).
    """
    from core.diagnostic_engine import CLASS_DISPLAY_NAMES

    client_ip = _client_ip(req)
    check_diagnosis_rate_limit(user, client_ip)

    db = get_db_manager()

    # Build vehicle intake from selected vehicle (optional)
    vehicle_intake = None
    selected = db.get_selected_vehicle()
    if selected:
        vehicle_intake = VehicleIntake(
            year=selected.get("model_year"),
            make=selected.get("make", "") or "",
            model=selected.get("model", "") or "",
            engine=selected.get("submodel", "") or "",
        )

    # Load audio from uploaded file (WAV, MP3, MP4, FLAC, OGG, WEBM)
    try:
        from core.audio_io import load_audio_bytes
        audio_bytes = await audio_file.read()
        filename = getattr(audio_file, "filename", None) or "audio"
        audio_data, sr = load_audio_bytes(audio_bytes, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid audio file: {e}")

    code_list = [c.strip() for c in codes.split(",") if c.strip()]

    try:
        result = run_diagnosis(
            audio=audio_data,
            sr=sr,
            codes=code_list,
            symptoms=symptoms,
            db_manager=db,
            vehicle_intake=vehicle_intake,
            plain_english=plain_english,
        )
    except Exception as e:
        logger.error("Audio diagnosis failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    increment_diagnosis_count(user, client_ip)

    report_text = export_report(result)
    ranked = getattr(result, "ranked_failure_modes", None) or []

    return DiagnosisResponse(
        top_class=result.top_class,
        top_class_display=CLASS_DISPLAY_NAMES.get(result.top_class, result.top_class),
        confidence=result.confidence,
        is_ambiguous=result.is_ambiguous,
        class_scores=[
            ClassScore(
                class_name=cls,
                display_name=CLASS_DISPLAY_NAMES.get(cls, cls),
                score=score,
                penalty=result.penalties_applied.get(cls, 0.0),
            )
            for cls, score in sorted(
                result.class_scores.items(), key=lambda x: x[1], reverse=True
            )
        ],
        fingerprint_count=result.fingerprint_count,
        llm_narrative=result.llm_narrative,
        report_text=report_text,
        ranked_failure_modes=[
            RankedFailureMode(
                failure_id=m.failure_id,
                display_name=m.display_name,
                description=m.description,
                score=m.score,
                confirm_tests=getattr(m, "confirm_tests", []) or [],
                matched_conditions=getattr(m, "matched_conditions", []) or [],
                ruled_out_disqualifiers=getattr(m, "ruled_out_disqualifiers", []) or [],
            )
            for m in ranked
        ],
    )


@router.post("/confirm", response_model=ConfirmTestResponse)
async def confirm_test(request: ConfirmTestRequest):
    """
    Apply a confirm test result (pass/fail) and return re-ranked failure modes.
    Client sends current ranked_failure_modes, test_id (e.g. overnight_pressure_test), and result.
    """
    from core.failure_pattern_engine import FailureModeMatch, apply_confirm_test

    current = [
        FailureModeMatch(
            failure_id=m.failure_id,
            display_name=m.display_name,
            description=m.description,
            score=m.score,
            confirm_tests=m.confirm_tests,
            matched_conditions=m.matched_conditions,
            ruled_out_disqualifiers=m.ruled_out_disqualifiers,
        )
        for m in request.ranked_failure_modes
    ]
    updated = apply_confirm_test(current, request.test_id, request.result)
    return ConfirmTestResponse(
        ranked_failure_modes=[
            RankedFailureMode(
                failure_id=m.failure_id,
                display_name=m.display_name,
                description=m.description,
                score=m.score,
                confirm_tests=m.confirm_tests,
                matched_conditions=m.matched_conditions,
                ruled_out_disqualifiers=m.ruled_out_disqualifiers,
            )
            for m in updated
        ],
    )
