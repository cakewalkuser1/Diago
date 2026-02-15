"""
Build canonical DiagnosticIntake from current API inputs (symptoms text, codes, context, vehicle).
Used by run_diagnosis to feed the failure-pattern layer while keeping backward compatibility.
"""

from core.models import (
    DiagnosticIntake,
    VehicleIntake,
    FuelTrimIntake,
    EnvironmentIntake,
)


def build_diagnostic_intake(
    symptoms_text: str,
    codes: list[str],
    context,
    vehicle_intake: VehicleIntake | None = None,
    fuel_trims: FuelTrimIntake | None = None,
) -> DiagnosticIntake:
    """
    Build structured DiagnosticIntake from free-text symptoms, DTCs, behavioral context,
    and optional vehicle/fuel trim data.
    """
    vehicle = vehicle_intake or VehicleIntake()

    # Parse symptoms to normalized list (keywords + phrases)
    symptoms_list = []
    if symptoms_text and symptoms_text.strip():
        parsed = _parse_symptoms_to_list(symptoms_text, context)
        symptoms_list = parsed

    # Environment from BehavioralContext
    env = EnvironmentIntake(
        cold_start=getattr(context, "cold_only", False),
        at_idle=getattr(context, "occurs_at_idle", False),
        under_load=getattr(context, "load_dependency", False),
    )

    return DiagnosticIntake(
        vehicle=vehicle,
        symptoms=symptoms_list,
        dtcs=[c.strip().upper() for c in codes if c and c.strip()],
        fuel_trims=fuel_trims or FuelTrimIntake(),
        environment=env,
    )


def _parse_symptoms_to_list(symptoms_text: str, context) -> list[str]:
    """
    Convert free-text symptoms and context into a list of normalized condition keys
    for pattern matching. Uses symptom parser when available; otherwise tokenize.
    """
    try:
        from core.symptom_parser import parse_symptoms
        parsed = parse_symptoms(symptoms_text)
        if not parsed:
            return _tokenize_symptoms(symptoms_text)
        out = []
        # Use matched keywords as symptom keys (normalize to lowercase with underscores)
        for kw in parsed.matched_keywords or []:
            out.append(kw.lower().replace(" ", "_").replace("-", "_"))
        # Add context-derived keys
        if getattr(context, "cold_only", False):
            out.append("cold_start")
        if getattr(context, "occurs_at_idle", False):
            out.append("at_idle")
        if getattr(context, "noise_character", "unknown") != "unknown":
            out.append(f"noise_{context.noise_character}")
        # Common phrase mappings for pattern DB
        text_lower = (symptoms_text or "").lower()
        if "coolant" in text_lower and ("loss" in text_lower or "low" in text_lower):
            out.append("coolant_loss")
        if "misfire" in text_lower and "cold" in text_lower:
            out.append("cold_start_misfire")
        if "misfire" in text_lower:
            out.append("misfire")
        if "rough" in text_lower and "cold" in text_lower:
            out.append("rough_cold_start")
        if "squeal" in text_lower or "squeak" in text_lower:
            out.append("squeal_cold")
            out.append("belt_noise")
        if "bearing" in text_lower or "growl" in text_lower or "rumble" in text_lower:
            out.append("bearing_noise")
            out.append("speed_dependent")
        if "hiss" in text_lower or "vacuum" in text_lower:
            out.append("hissing_noise")
        if "lean" in text_lower or "trim" in text_lower:
            out.append("lean_trim_above_15")
        if "rich" in text_lower:
            out.append("rich_at_idle")
        return list(dict.fromkeys(out))  # dedupe, preserve order
    except Exception:
        return _tokenize_symptoms(symptoms_text)


def _tokenize_symptoms(text: str) -> list[str]:
    """Fallback: split by comma/semicolon and normalize."""
    if not text or not text.strip():
        return []
    parts = []
    for part in text.replace(";", ",").split(","):
        t = part.strip().lower().replace(" ", "_")
        if t and len(t) > 1:
            parts.append(t)
    return parts
