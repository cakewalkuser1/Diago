"""
Failure pattern recognition and scoring (master-tech layer).
Scores failure modes from structured DiagnosticIntake using required/supporting
conditions, disqualifiers, and fuel-trim-derived rules.
"""

from dataclasses import dataclass
from typing import Any

from core.models import DiagnosticIntake, FuelTrimIntake, EnvironmentIntake, VehicleIntake


# Single-cylinder misfire DTCs: if any present, add "single_cylinder_misfire" to conditions
SINGLE_CYL_MISFIRE_DTCS = frozenset({"P0301", "P0302", "P0303", "P0304", "P0305", "P0306"})


@dataclass
class FailureModeMatch:
    """One ranked failure mode with score and confirm tests."""
    failure_id: str
    display_name: str
    description: str
    score: float
    confirm_tests: list[dict]
    matched_conditions: list[str]
    ruled_out_disqualifiers: list[str]


def get_fuel_trim_conditions(fuel_trims: FuelTrimIntake, environment: EnvironmentIntake) -> list[str]:
    """
    Derive condition keys from fuel trim data and environment (idle/load).
    Used so failure patterns can reference e.g. lean_trim_above_15, both_banks_lean_idle.
    """
    conditions = []
    stft = fuel_trims.stft if fuel_trims else None
    ltft = fuel_trims.ltft if fuel_trims else None
    stft_val = stft if stft is not None else 0.0
    ltft_val = ltft if ltft is not None else 0.0
    combined = max(abs(stft_val), abs(ltft_val))

    if combined >= 15:
        conditions.append("lean_trim_above_15")
    if combined >= 20 and getattr(environment, "at_idle", False):
        conditions.append("both_banks_lean_idle")
    if getattr(environment, "under_load", False) and combined >= 15:
        conditions.append("lean_under_load_only")
    if stft_val <= -10 and getattr(environment, "at_idle", False):
        conditions.append("rich_at_idle")

    return conditions


def _vehicle_scope_slug(vehicle: VehicleIntake) -> str:
    """Build a slug like 'toyota_camry_2arfe' for vehicle_scope matching."""
    if not vehicle:
        return ""
    make = (getattr(vehicle, "make", None) or "").strip().lower().replace(" ", "_")
    model = (getattr(vehicle, "model", None) or "").strip().lower().replace(" ", "_")
    engine = (getattr(vehicle, "engine", None) or "").strip().lower().replace(" ", "_")
    parts = [p for p in [make, model, engine] if p]
    return "_".join(parts) if parts else ""


def build_active_conditions(intake: DiagnosticIntake) -> set[str]:
    """
    Build the set of active condition keys from intake (DTCs, symptoms, environment, fuel trim).
    """
    active = set()
    # DTCs (normalized uppercase)
    for c in intake.dtcs or []:
        active.add((c or "").strip().upper())
    # Symptoms (normalized)
    for s in intake.symptoms or []:
        active.add((s or "").strip().lower())
    # Environment
    env = intake.environment or EnvironmentIntake()
    if getattr(env, "cold_start", False):
        active.add("cold_start")
    if getattr(env, "at_idle", False):
        active.add("at_idle")
    if getattr(env, "under_load", False):
        active.add("under_load")
    # Fuel trim-derived
    for cond in get_fuel_trim_conditions(intake.fuel_trims or FuelTrimIntake(), env):
        active.add(cond)
    # Single-cylinder misfire: if any P0301–P0306 present
    if any(d in active for d in SINGLE_CYL_MISFIRE_DTCS):
        active.add("single_cylinder_misfire")
    return active


def score_failure_modes(
    intake: DiagnosticIntake | None,
    failure_modes: list[dict],
) -> list[FailureModeMatch]:
    """
    Score and rank failure modes from structured intake.
    Returns list of FailureModeMatch sorted by score descending (zeros excluded).
    """
    if not intake:
        return []
    active = build_active_conditions(intake)
    # Normalize for matching: lowercase string comparison
    active_lower = {str(x).lower() for x in active}
    active_upper = {str(x).upper() for x in active}

    def in_active(cond: str) -> bool:
        c = (cond or "").strip()
        if not c:
            return False
        return c.lower() in active_lower or c.upper() in active_upper or c in active

    results = []
    for fm in failure_modes:
        failure_id = fm.get("failure_id") or ""
        required = fm.get("required_conditions") or []
        supporting = fm.get("supporting_conditions") or []
        disqualifiers = fm.get("disqualifiers") or []
        weight = float(fm.get("weight") or 0.8)
        confirm_tests = fm.get("confirm_tests") or []

        ruled_out = [d for d in disqualifiers if in_active(d)]
        if ruled_out:
            results.append(FailureModeMatch(
                failure_id=failure_id,
                display_name=fm.get("display_name") or failure_id,
                description=fm.get("description") or "",
                score=0.0,
                confirm_tests=confirm_tests,
                matched_conditions=[],
                ruled_out_disqualifiers=ruled_out,
            ))
            continue

        num_required = len(required)
        matched_req = sum(1 for r in required if in_active(r))
        if num_required == 0:
            score_ratio = 1.0
        else:
            score_ratio = matched_req / num_required

        num_supporting = len(supporting)
        matched_sup = sum(1 for s in supporting if in_active(s)) if supporting else 0
        support_bonus = 0.0
        if num_supporting > 0:
            support_bonus = 0.15 * (matched_sup / num_supporting)

        score = min(1.0, score_ratio * weight + support_bonus)
        if score <= 0:
            continue

        # Optional: boost platform-specific failure modes when vehicle matches
        vehicle_scope = fm.get("vehicle_scope")
        if vehicle_scope and intake.vehicle:
            slug = _vehicle_scope_slug(intake.vehicle)
            if slug and vehicle_scope.lower().strip() == slug.lower():
                score = min(1.0, round(score + 0.05, 4))

        matched_conditions = [r for r in required if in_active(r)] + [s for s in supporting if in_active(s)]
        results.append(FailureModeMatch(
            failure_id=failure_id,
            display_name=fm.get("display_name") or failure_id,
            description=fm.get("description") or "",
            score=round(score, 4),
            confirm_tests=confirm_tests,
            matched_conditions=matched_conditions,
            ruled_out_disqualifiers=[],
        ))

    results.sort(key=lambda x: x.score, reverse=True)
    return results


# Default bonus/penalty magnitudes — overridden per test by "confidence_weight" field.
# confidence_weight in a confirm_test entry scales these: 1.0 = full, 0.5 = half, etc.
# Example: leakdown test (confidence_weight 1.2) is more diagnostic than visual (0.6).
CONFIRM_PASS_BONUS = 0.15
CONFIRM_FAIL_PENALTY = 0.35


def apply_confirm_test(
    ranked_failure_modes: list[FailureModeMatch],
    test_id: str,
    result: str,
) -> list[FailureModeMatch]:
    """
    Update scores based on a confirm test result (pass/fail), then re-sort.

    test_id must match the "test" field in a failure mode's confirm_tests list.
    result: "pass" | "fail" (also accepts yes/no/true/false/1/0).

    Each confirm_test entry may include an optional "confidence_weight" (float,
    default 1.0) that scales the pass bonus / fail penalty, so high-diagnostic-
    value tests (leakdown, smoke machine) move the score more than visual checks.
    """
    if not test_id or not result:
        return list(ranked_failure_modes)
    result_lower = result.strip().lower()
    is_pass = result_lower in ("pass", "yes", "true", "1")
    is_fail = result_lower in ("fail", "no", "false", "0")
    if not is_pass and not is_fail:
        return list(ranked_failure_modes)

    updated = []
    for fm in ranked_failure_modes:
        tests = fm.confirm_tests or []
        matched_test = next(
            (t for t in tests if isinstance(t, dict) and t.get("test") == test_id),
            None,
        )
        if matched_test is None:
            updated.append(FailureModeMatch(
                failure_id=fm.failure_id,
                display_name=fm.display_name,
                description=fm.description,
                score=fm.score,
                confirm_tests=fm.confirm_tests,
                matched_conditions=fm.matched_conditions,
                ruled_out_disqualifiers=fm.ruled_out_disqualifiers,
            ))
            continue

        # Scale bonus/penalty by per-test confidence_weight (default 1.0)
        cw = float(matched_test.get("confidence_weight") or 1.0)
        cw = max(0.1, min(cw, 2.0))  # clamp to sane range
        if is_pass:
            delta = CONFIRM_PASS_BONUS * cw
        else:
            delta = -(CONFIRM_FAIL_PENALTY * cw)

        new_score = max(0.0, min(1.0, fm.score + delta))
        updated.append(FailureModeMatch(
            failure_id=fm.failure_id,
            display_name=fm.display_name,
            description=fm.description,
            score=round(new_score, 4),
            confirm_tests=fm.confirm_tests,
            matched_conditions=fm.matched_conditions,
            ruled_out_disqualifiers=fm.ruled_out_disqualifiers,
        ))
    updated.sort(key=lambda x: x.score, reverse=True)
    return updated


def fuse_with_audio_scores(
    ranked_failure_modes: list[FailureModeMatch],
    audio_class_scores: dict[str, float],
    fusion_weight: float = 0.25,
) -> list[FailureModeMatch]:
    """
    Blend failure-mode pattern scores with audio mechanical-class scores.

    When the audio engine and the DTC/symptom pattern engine agree on a class,
    the combined evidence should yield higher confidence than either alone.
    When they disagree, the score is modestly dampened.

    Args:
        ranked_failure_modes: Output of score_failure_modes().
        audio_class_scores: Normalized class probabilities from diagnostic_engine
                            (keys are MECHANICAL_CLASSES strings, values 0-1).
        fusion_weight: How much the audio agreement/disagreement shifts the score.
                       0.25 means audio can add/remove up to 0.25 * audio_score.

    Returns:
        Re-scored and re-sorted failure mode list.
    """
    if not audio_class_scores or not ranked_failure_modes:
        return list(ranked_failure_modes)

    fused = []
    for fm in ranked_failure_modes:
        if fm.score <= 0:
            fused.append(fm)
            continue
        mech_class = fm.failure_id  # fallback: no class match → neutral
        # FailureModeMatch doesn't store mechanical_class directly; look it up
        # by iterating audio_class_scores for a rough match via display hints.
        # Best-effort: if the fm.failure_id contains a class keyword, use it.
        audio_support = 0.0
        for cls, cls_score in audio_class_scores.items():
            cls_slug = cls.lower()
            fm_slug = fm.failure_id.lower()
            fm_display = fm.display_name.lower()
            if (cls_slug in fm_slug or
                    any(word in fm_display for word in cls_slug.replace("_", " ").split())):
                audio_support = cls_score
                break

        # Agreement: audio_support > 0 → small boost; silence/disagreement → neutral/slight damp
        adjustment = fusion_weight * (audio_support - 0.14)  # 0.14 ≈ uniform prior for 7 classes
        new_score = max(0.0, min(1.0, fm.score + adjustment))
        fused.append(FailureModeMatch(
            failure_id=fm.failure_id,
            display_name=fm.display_name,
            description=fm.description,
            score=round(new_score, 4),
            confirm_tests=fm.confirm_tests,
            matched_conditions=fm.matched_conditions,
            ruled_out_disqualifiers=fm.ruled_out_disqualifiers,
        ))

    fused.sort(key=lambda x: x.score, reverse=True)
    return fused
