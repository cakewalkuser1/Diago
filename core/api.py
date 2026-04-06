"""
Diago Core API Facade
Clean, high-level interface to all core operations.
This module is the single entry point for the FastAPI service (Phase 2)
and for any future UI layer.

All functions are stateless and operate on explicit inputs/outputs.
Database connections are managed via the DatabaseManager passed in.
"""

import logging
from pathlib import Path
from typing import Optional

import numpy as np

from core.config import get_settings
from core.models import (
    DiagnosisResult,
    FaultSignature,
    AnalysisSession,
    MatchResult,
    CodeDefinition,
    Fingerprint,
    VehicleIntake,
    FuelTrimIntake,
)
from core.feature_extraction import BehavioralContext, AudioFeatures

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Audio Operations
# ---------------------------------------------------------------------------

def load_audio(path: str) -> tuple[np.ndarray, int]:
    """
    Load an audio file and return normalized mono float32 data.

    Args:
        path: Path to audio file (WAV, MP3, FLAC, OGG).

    Returns:
        Tuple of (audio_data, sample_rate).

    Raises:
        FileNotFoundError: If file doesn't exist.
        ValueError: If format is unsupported.
    """
    from core.audio_io import load_audio_file
    logger.info("Loading audio from %s", path)
    data, sr = load_audio_file(path)
    logger.info("Loaded %.2fs of audio at %d Hz", len(data) / sr, sr)
    return data, sr


def save_audio(data: np.ndarray, path: str, sample_rate: int = 44100) -> None:
    """Save audio data to a WAV file."""
    from core.audio_io import save_audio as _save
    _save(data, path, sample_rate)
    logger.info("Saved audio to %s", path)


def record_audio(duration: float, sample_rate: int = 44100) -> np.ndarray:
    """
    Record audio from the default microphone.

    Args:
        duration: Recording duration in seconds.
        sample_rate: Sample rate in Hz.

    Returns:
        Mono float32 numpy array.
    """
    from core.audio_io import record_audio as _record
    logger.info("Recording %ss of audio at %d Hz", duration, sample_rate)
    data = _record(duration, sample_rate)
    logger.info("Recorded %d samples", len(data))
    return data


# ---------------------------------------------------------------------------
# Spectrogram Operations
# ---------------------------------------------------------------------------

def generate_spectrogram(
    audio: np.ndarray,
    sr: int = 44100,
    mode: str = "stft",
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute a spectrogram from audio data.

    Args:
        audio: Mono float32 audio array.
        sr: Sample rate.
        mode: "stft", "mel", or "power".

    Returns:
        Tuple of (frequencies, times, spectrogram_data).
    """
    from core.spectrogram import (
        compute_spectrogram,
        compute_mel_spectrogram,
        compute_power_spectrogram,
    )

    if mode == "mel":
        return compute_mel_spectrogram(audio, sr)
    elif mode == "power":
        return compute_power_spectrogram(audio, sr)
    else:
        return compute_spectrogram(audio, sr)


# ---------------------------------------------------------------------------
# Diagnosis Operations
# ---------------------------------------------------------------------------

def run_diagnosis(
    audio: Optional[np.ndarray],
    sr: int,
    codes: list[str],
    symptoms: str,
    context: Optional[BehavioralContext] = None,
    db_manager=None,
    progress_callback=None,
    vehicle_intake: Optional[VehicleIntake] = None,
    plain_english: bool = False,
    fuel_trims: Optional[FuelTrimIntake] = None,
) -> DiagnosisResult:
    """
    Run the full diagnostic pipeline.

    Automatically routes to audio or text-only pipeline based on input.
    Builds structured DiagnosticIntake for the failure-pattern layer (master-tech).
    """
    from core.symptom_parser import parse_symptoms
    from core.diagnostic_engine import run_diagnostic_pipeline_auto
    from core.diagnostic_intake import build_diagnostic_intake

    # Parse symptoms to extract context and class hints
    parsed = parse_symptoms(symptoms) if symptoms else None

    # Build or merge behavioral context
    if context is None:
        context = parsed.context if parsed else BehavioralContext()
    elif parsed:
        # Merge: GUI context takes priority on non-default fields
        context = _merge_contexts(context, parsed.context)

    class_hints = parsed.class_hints if parsed else {}
    symptom_confidence = parsed.confidence if parsed else 0.0

    # Structured intake for pattern layer (backward compatible: no vehicle required)
    diagnostic_intake = build_diagnostic_intake(
        symptoms_text=symptoms or "",
        codes=codes or [],
        context=context,
        vehicle_intake=vehicle_intake,
        fuel_trims=fuel_trims,
    )

    settings = get_settings()

    logger.info(
        "Running diagnosis: audio=%s, codes=%s, has_symptoms=%s",
        "yes" if audio is not None else "no",
        codes,
        bool(symptoms),
    )

    result = run_diagnostic_pipeline_auto(
        audio_data=audio,
        sr=sr,
        context=context,
        class_hints=class_hints,
        user_codes=codes,
        db_manager=db_manager,
        symptom_confidence=symptom_confidence,
        llm_enabled=settings.llm.llm_enabled,
        progress_callback=progress_callback,
        plain_english=plain_english,
    )

    # Attach structured intake for pattern engine and API (Phase 2)
    result.diagnostic_intake = diagnostic_intake

    # Rank failure modes from pattern layer (master-tech)
    if db_manager and getattr(result, "diagnostic_intake", None):
        from core.failure_pattern_engine import score_failure_modes, fuse_with_audio_scores
        failure_modes = db_manager.get_failure_modes()
        ranked = score_failure_modes(
            result.diagnostic_intake,
            failure_modes,
        )
        # Fuse with audio class scores when audio was recorded (improves accuracy
        # when both the sound and the DTC/symptom evidence agree on a class).
        audio_scores = getattr(result, "class_scores", None)
        if audio_scores:
            ranked = fuse_with_audio_scores(ranked, audio_scores)
        result.ranked_failure_modes = ranked

    # Optional: extend LLM narrative with failure-mode explanation (Phase 4)
    if getattr(result, "ranked_failure_modes", None):
        try:
            from core.llm_reasoning import enhance_narrative_with_failure_modes
            enhance_narrative_with_failure_modes(result, plain_english=plain_english)
        except Exception as e:
            logger.warning("Failure-mode narrative enhancement failed: %s", e)

    logger.info(
        "Diagnosis complete: top_class=%s, confidence=%s, ambiguous=%s",
        result.top_class, result.confidence, result.is_ambiguous,
    )

    return result


# ---------------------------------------------------------------------------
# Session Operations
# ---------------------------------------------------------------------------

def save_session(
    db_manager,
    audio_path: str = "",
    user_codes: str = "",
    notes: str = "",
    duration_seconds: float = 0.0,
    matches: list[MatchResult] | None = None,
) -> int:
    """
    Save an analysis session to the database.

    Args:
        db_manager: Database manager instance.
        audio_path: Path to the audio file (if any).
        user_codes: Comma-separated OBD-II codes.
        notes: User notes or diagnostic summary.
        duration_seconds: Audio duration.
        matches: Optional list of match results to save.

    Returns:
        The new session ID.
    """
    session_id = db_manager.create_session(
        audio_path=audio_path,
        user_codes=user_codes,
        notes=notes,
        duration_seconds=duration_seconds,
    )

    if matches:
        for match in matches:
            if match.signature_id > 0:
                db_manager.add_session_match(
                    session_id=session_id,
                    signature_id=match.signature_id,
                    confidence=match.confidence_pct,
                )

    logger.info("Saved session %d with %d matches", session_id, len(matches or []))
    return session_id


def get_session_history(db_manager, limit: int = 50) -> list[AnalysisSession]:
    """Retrieve recent analysis sessions."""
    return db_manager.get_session_history(limit)


# ---------------------------------------------------------------------------
# Report Operations
# ---------------------------------------------------------------------------

def export_report(
    result: DiagnosisResult,
    format: str = "text",
) -> str:
    """
    Generate a diagnostic report from analysis results.

    Args:
        result: DiagnosisResult from run_diagnosis.
        format: "text" (more formats coming in future phases).

    Returns:
        Report as a string.
    """
    from core.diagnostic_engine import CLASS_DISPLAY_NAMES
    from core.llm_reasoning import generate_fallback_narrative

    lines = []
    lines.append("=" * 60)
    lines.append("DIAGO DIAGNOSTIC REPORT")
    lines.append("=" * 60)
    lines.append("")

    # Top classification
    top_display = CLASS_DISPLAY_NAMES.get(result.top_class, result.top_class)
    lines.append(f"Primary Diagnosis: {top_display}")
    lines.append(f"Confidence: {result.confidence}")
    lines.append(f"Ambiguous: {'Yes' if result.is_ambiguous else 'No'}")
    lines.append("")

    # Class scores
    lines.append("--- Mechanical Class Scores ---")
    sorted_scores = sorted(
        result.class_scores.items(), key=lambda x: x[1], reverse=True
    )
    for cls, score in sorted_scores:
        display = CLASS_DISPLAY_NAMES.get(cls, cls)
        penalty = result.penalties_applied.get(cls, 0.0)
        penalty_str = f" (penalty: {penalty:.2f})" if penalty > 0 else ""
        lines.append(f"  {display}: {score:.1%}{penalty_str}")
    lines.append("")

    # Narrative
    lines.append("--- Analysis ---")
    if result.llm_narrative:
        lines.append(result.llm_narrative)
    else:
        narrative = generate_fallback_narrative(
            result.class_scores,
            result.features,
            result.penalties_applied,
            result.is_ambiguous,
        )
        lines.append(narrative)
    lines.append("")

    # Fingerprint matches
    if result.fingerprint_matches:
        lines.append("--- Fingerprint Matches ---")
        for match in result.fingerprint_matches:
            lines.append(
                f"  {match.fault_name}: {match.confidence_pct:.1f}% "
                f"[{match.category}] {match.trouble_codes}"
            )
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Code Lookup Operations
# ---------------------------------------------------------------------------

def lookup_trouble_code(code: str, db_manager) -> Optional[CodeDefinition]:
    """Look up a single OBD-II trouble code."""
    from database.trouble_code_lookup import lookup_code
    return lookup_code(code, db_manager)


def lookup_trouble_codes(codes: list[str], db_manager) -> list[CodeDefinition]:
    """Look up multiple OBD-II trouble codes."""
    from database.trouble_code_lookup import lookup_codes
    return lookup_codes(codes, db_manager)


def search_trouble_codes(query: str, db_manager) -> list[CodeDefinition]:
    """Free-text search across trouble code definitions."""
    from database.trouble_code_lookup import search_codes
    return search_codes(query, db_manager)


# ---------------------------------------------------------------------------
# Signature Operations
# ---------------------------------------------------------------------------

def get_all_signatures(db_manager) -> list[FaultSignature]:
    """Get all fault signatures from the database."""
    return db_manager.get_all_signatures()


def add_signature(
    db_manager,
    name: str,
    description: str,
    category: str,
    associated_codes: str,
    audio_data: Optional[np.ndarray] = None,
    sr: int = 44100,
) -> int:
    """
    Add a new fault signature, optionally with audio fingerprints.

    Returns:
        The new signature ID.
    """
    sig_id = db_manager.add_fault_signature(
        name=name,
        description=description,
        category=category,
        associated_codes=associated_codes,
    )

    if audio_data is not None and len(audio_data) > 0:
        from core.preprocessing import preprocess_audio
        from core.fingerprint import generate_fingerprint

        conditioned = preprocess_audio(audio_data, sr)
        fingerprints = generate_fingerprint(conditioned, sr)
        hashes = [(fp.hash_value, fp.time_offset) for fp in fingerprints]
        db_manager.add_signature_hashes(sig_id, hashes)
        logger.info("Added signature %d with %d fingerprint hashes", sig_id, len(hashes))
    else:
        logger.info("Added signature %d (no audio)", sig_id)

    return sig_id


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _merge_contexts(
    gui_context: BehavioralContext,
    parsed_context: BehavioralContext,
) -> BehavioralContext:
    """
    Merge GUI context with symptom-parsed context.
    GUI values take priority for non-default fields.
    """
    merged = BehavioralContext()

    # Boolean fields: GUI wins if True
    merged.rpm_dependency = gui_context.rpm_dependency or parsed_context.rpm_dependency
    merged.speed_dependency = gui_context.speed_dependency or parsed_context.speed_dependency
    merged.load_dependency = gui_context.load_dependency or parsed_context.load_dependency
    merged.cold_only = gui_context.cold_only or parsed_context.cold_only
    merged.occurs_at_idle = gui_context.occurs_at_idle or parsed_context.occurs_at_idle
    merged.mechanical_localization = (
        gui_context.mechanical_localization or parsed_context.mechanical_localization
    )
    merged.intermittent = gui_context.intermittent or parsed_context.intermittent

    # Categorical fields: GUI wins if not "unknown"
    merged.noise_character = (
        gui_context.noise_character
        if gui_context.noise_character != "unknown"
        else parsed_context.noise_character
    )
    merged.perceived_frequency = (
        gui_context.perceived_frequency
        if gui_context.perceived_frequency != "unknown"
        else parsed_context.perceived_frequency
    )
    merged.issue_duration = (
        gui_context.issue_duration
        if gui_context.issue_duration != "unknown"
        else parsed_context.issue_duration
    )
    merged.vehicle_type = (
        gui_context.vehicle_type
        if gui_context.vehicle_type != "unknown"
        else parsed_context.vehicle_type
    )
    merged.mileage_range = (
        gui_context.mileage_range
        if gui_context.mileage_range != "unknown"
        else parsed_context.mileage_range
    )
    merged.recent_maintenance = (
        gui_context.recent_maintenance
        if gui_context.recent_maintenance != "unknown"
        else parsed_context.recent_maintenance
    )

    return merged
