"""
Diagnostic Engine (v2 -- Accuracy Upgrade)
The central brain of the analysis pipeline.

Implements:
1. Sigmoid-scaled mechanical class scoring with tunable decision boundaries
2. Feature interaction terms (cross-feature combinations)
3. Negative evidence (counter-weights that argue against a class)
4. Proportional physics constraint penalties (scaled by violation distance)
5. Confidence margin check (gap between #1 and #2 matters)
6. Full pipeline orchestration

System Guarantee:
    No class can win if it violates physics constraints,
    even if the LLM attempts to favor it.
"""

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from core.preprocessing import preprocess_audio
from core.feature_extraction import (
    extract_features, extract_features_from_context,
    AudioFeatures, BehavioralContext,
)
from core.fingerprint import generate_fingerprint, compute_fingerprint_stats
from core.matcher import match_with_trouble_codes
from database.db_manager import DatabaseManager, MatchResult


# ---------------------------------------------------------------------------
# Mechanical Classes
# ---------------------------------------------------------------------------

MECHANICAL_CLASSES = [
    "rolling_element_bearing",
    "gear_mesh_drivetrain",
    "belt_drive_friction",
    "hydraulic_flow_cavitation",
    "electrical_interference",
    "combustion_impulse",
    "structural_resonance",
]

CLASS_DISPLAY_NAMES = {
    "rolling_element_bearing": "Rolling Element Bearing",
    "gear_mesh_drivetrain": "Gear Mesh / Drivetrain",
    "belt_drive_friction": "Belt Drive / Friction",
    "hydraulic_flow_cavitation": "Hydraulic Flow / Cavitation",
    "electrical_interference": "Electrical Interference",
    "combustion_impulse": "Combustion Impulse",
    "structural_resonance": "Structural Resonance",
}

CLASS_DESCRIPTIONS = {
    "rolling_element_bearing": (
        "Worn or failing bearing (wheel, idler pulley, alternator, water pump). "
        "Characterized by broadband noise with potential periodicity."
    ),
    "gear_mesh_drivetrain": (
        "Gear mesh noise from differential, transmission, or transfer case. "
        "Characterized by strong harmonics that vary with speed."
    ),
    "belt_drive_friction": (
        "Serpentine belt, tensioner, or accessory drive friction. "
        "Characterized by squealing or chirping, often worse at cold start."
    ),
    "hydraulic_flow_cavitation": (
        "Hydraulic pump cavitation or fluid flow noise (power steering, "
        "transmission cooler). Whining that varies with load."
    ),
    "electrical_interference": (
        "Electrical whine from alternator, fuel pump, or other electrical "
        "components. Tonal, often RPM-dependent."
    ),
    "combustion_impulse": (
        "Combustion-related noise: misfire, knock, detonation, injector tick. "
        "Impulsive, synchronized with engine firing events."
    ),
    "structural_resonance": (
        "Structural vibration, resonance, or loose components. Clunks, "
        "rattles, and buzzes triggered by road or engine excitation."
    ),
}


# ---------------------------------------------------------------------------
# Sigmoid scaling
# ---------------------------------------------------------------------------

def sigmoid_scale(
    value: float,
    midpoint: float = 0.5,
    steepness: float = 10.0,
) -> float:
    """
    Map a [0,1] feature value through a sigmoid for sharper decision boundaries.

    Below midpoint -> near 0, above midpoint -> near 1.
    Steepness controls how sharp the transition is.
    """
    return 1.0 / (1.0 + np.exp(-steepness * (value - midpoint)))


# ---------------------------------------------------------------------------
# Feature Weights per Class (tunable configuration)
# ---------------------------------------------------------------------------

# Each entry: (feature_name, weight, midpoint, steepness)
# Positive weight = feature supports this class
# Negative weight = feature argues AGAINST this class (negative evidence)

FEATURE_WEIGHTS: dict[str, list[tuple[str, float, float, float]]] = {
    "rolling_element_bearing": [
        # Positive evidence
        ("spectral_flatness", 0.7, 0.3, 10.0),      # Bearings = broadband
        ("band_mid", 0.5, 0.25, 10.0),               # 1-3kHz dominant
        ("band_high_mid", 0.4, 0.15, 10.0),          # 3-6kHz harmonics
        ("crest_factor", 0.4, 0.3, 8.0),             # Spalling = impulsive
        ("periodicity_score", 0.5, 0.2, 8.0),        # Rolling elements = rhythmic
        ("cold_only", 0.5, 0.5, 20.0),               # Cold grease = louder
        ("speed_dependency", 0.4, 0.5, 20.0),        # Wheel/axle bearing
        ("rpm_dependency", 0.4, 0.5, 20.0),          # Engine accessory bearing
        ("mileage_over_150k", 0.3, 0.5, 20.0),       # High mileage = worn bearings
        ("char_hum_drone", 0.4, 0.5, 20.0),          # Bearing = hum/drone
        ("char_grind_scrape", 0.5, 0.5, 20.0),       # Severe bearing = grinding
        # Negative evidence
        ("harmonic_ratio", -0.5, 0.5, 10.0),         # Bearings are NOT tonal
        ("char_squeal", -0.3, 0.5, 20.0),            # Squeal = belt, not bearing
        ("char_knock_tap", -0.3, 0.5, 20.0),         # Knocking = combustion
    ],
    "gear_mesh_drivetrain": [
        # Positive evidence
        ("harmonic_ratio", 0.8, 0.35, 12.0),         # Strong harmonics
        ("speed_dependency", 0.6, 0.5, 20.0),        # Tracks vehicle speed
        ("periodicity_score", 0.5, 0.3, 10.0),       # Periodic mesh frequency
        ("load_dependency", 0.4, 0.5, 20.0),         # Louder under load
        ("band_low_mid", 0.5, 0.2, 10.0),            # 300-1000 Hz gear mesh
        ("spectral_centroid_std", -0.3, 0.3, 10.0),  # Stable tonal = low std
        ("char_whine", 0.4, 0.5, 20.0),              # Gear whine
        ("char_hum_drone", 0.3, 0.5, 20.0),          # Differential drone
        # Negative evidence
        ("spectral_flatness", -0.5, 0.5, 10.0),      # Gear mesh is NOT broadband
        ("char_squeal", -0.4, 0.5, 20.0),            # Squeal = belt
        ("char_knock_tap", -0.3, 0.5, 20.0),         # Knocking = combustion
        ("char_rattle_buzz", -0.3, 0.5, 20.0),       # Rattle = structural
    ],
    "belt_drive_friction": [
        # Positive evidence
        ("spectral_centroid", 0.6, 0.15, 10.0),      # High-frequency squeal
        ("band_mid", 0.5, 0.25, 10.0),               # 1-3kHz belt squeal
        ("cold_only", 0.7, 0.5, 20.0),               # Much worse cold
        ("rpm_dependency", 0.5, 0.5, 20.0),          # Tracks engine RPM
        ("amplitude_variance", 0.4, 0.01, 15.0),     # Intermittent squeal
        ("periodicity_score", 0.3, 0.2, 8.0),        # Belt rotation period
        ("spectral_centroid_std", 0.3, 0.05, 12.0),  # Varying squeal pitch
        ("char_squeal", 0.7, 0.5, 20.0),             # User says "squeal"
        ("char_grind_scrape", 0.3, 0.5, 20.0),       # Could be chirp
        ("maint_belt_replacement", 0.3, 0.5, 20.0),  # Recent belt work
        ("freq_high", 0.3, 0.5, 20.0),               # Perceived high-pitched
        # Negative evidence
        ("spectral_flatness", -0.3, 0.6, 10.0),      # Belt is narrowband
        ("char_knock_tap", -0.5, 0.5, 20.0),         # Knocking = not belt
        ("char_rattle_buzz", -0.4, 0.5, 20.0),       # Rattle = not belt
    ],
    "hydraulic_flow_cavitation": [
        # Positive evidence
        ("spectral_centroid", 0.4, 0.1, 10.0),       # Mid-high whine
        ("load_dependency", 0.7, 0.5, 20.0),         # Worse under steering/brake
        ("rpm_dependency", 0.5, 0.5, 20.0),          # Pump RPM dependent
        ("spectral_flatness", 0.4, 0.25, 10.0),      # Cavitation = broadband
        ("band_mid", 0.4, 0.2, 10.0),                # 1-3kHz typical
        ("char_whine", 0.5, 0.5, 20.0),              # Pump whine
        ("char_hiss", 0.4, 0.5, 20.0),               # Flow hiss
        # Negative evidence
        ("transient_density", -0.3, 0.3, 10.0),      # Not impulsive
        ("char_knock_tap", -0.4, 0.5, 20.0),         # Not knocking
        ("char_rattle_buzz", -0.3, 0.5, 20.0),       # Not rattling
        ("char_squeal", -0.3, 0.5, 20.0),            # Not squealing
    ],
    "electrical_interference": [
        # Positive evidence
        ("harmonic_ratio", 0.6, 0.3, 12.0),          # Often tonal with harmonics
        ("rpm_dependency", 0.6, 0.5, 20.0),          # Alternator tracks RPM
        ("spectral_centroid", 0.5, 0.1, 10.0),       # Mid-high frequency
        ("band_high_mid", 0.4, 0.15, 10.0),          # 3-6kHz typical
        ("char_whine", 0.6, 0.5, 20.0),              # Electrical whine
        ("char_hiss", 0.3, 0.5, 20.0),               # Alternator hiss
        ("veh_hybrid_ev", 0.3, 0.5, 20.0),           # EVs have more electrical noise
        # Negative evidence
        ("amplitude_variance", -0.4, 0.3, 10.0),     # Electrical is steady
        ("spectral_flatness", -0.4, 0.5, 10.0),      # Electrical is tonal
        ("char_knock_tap", -0.5, 0.5, 20.0),         # Not knocking
        ("char_rattle_buzz", -0.5, 0.5, 20.0),       # Not rattling
        ("char_grind_scrape", -0.4, 0.5, 20.0),      # Not grinding
    ],
    "combustion_impulse": [
        # Positive evidence
        ("transient_density", 0.8, 0.1, 12.0),       # Impulsive: knocks, misfires
        ("crest_factor", 0.6, 0.25, 10.0),           # High crest = impulsive
        ("rpm_dependency", 0.6, 0.5, 20.0),          # Synchronized with engine
        ("occurs_at_idle", 0.5, 0.5, 20.0),          # Noticeable at idle
        ("periodicity_score", 0.5, 0.2, 8.0),        # Firing-order periodic
        ("load_dependency", 0.4, 0.5, 20.0),         # Knock worsens under load
        ("band_low", 0.4, 0.2, 10.0),                # Low-frequency impulses
        ("band_low_mid", 0.3, 0.2, 10.0),            # Low-mid too
        ("char_knock_tap", 0.8, 0.5, 20.0),          # User says "knock"
        ("char_click_tick", 0.5, 0.5, 20.0),         # Injector tick
        ("freq_low", 0.3, 0.5, 20.0),                # Perceived low frequency
        # Negative evidence
        ("spectral_flatness", -0.3, 0.6, 10.0),      # Not broadband noise
        ("char_whine", -0.4, 0.5, 20.0),             # Not whining
        ("char_squeal", -0.5, 0.5, 20.0),            # Not squealing
        ("char_hiss", -0.4, 0.5, 20.0),              # Not hissing
    ],
    "structural_resonance": [
        # Positive evidence
        ("amplitude_variance", 0.7, 0.01, 15.0),     # Intermittent rattles/clunks
        ("transient_density", 0.5, 0.1, 10.0),       # Impact events
        ("spectral_bandwidth", 0.5, 0.2, 10.0),      # Broadband impacts
        ("crest_factor", 0.4, 0.3, 8.0),             # Impulsive clunks
        ("mechanical_localization", 0.6, 0.5, 20.0),  # Pointable source
        ("speed_dependency", 0.4, 0.5, 20.0),        # Road-speed rattles
        ("band_low", 0.4, 0.2, 10.0),                # Low-frequency resonance
        ("intermittent", 0.5, 0.5, 20.0),            # Comes and goes
        ("char_rattle_buzz", 0.8, 0.5, 20.0),        # User says "rattle"
        ("char_knock_tap", 0.4, 0.5, 20.0),          # Clunk/knock variant
        ("maint_suspension_work", 0.3, 0.5, 20.0),   # Loose after suspension work
        # Negative evidence
        ("harmonic_ratio", -0.5, 0.4, 10.0),         # Not tonal
        ("char_whine", -0.5, 0.5, 20.0),             # Not whining
        ("char_squeal", -0.4, 0.5, 20.0),            # Not squealing
        ("char_hiss", -0.4, 0.5, 20.0),              # Not hissing
    ],
}


# ---------------------------------------------------------------------------
# Feature Interaction Terms
# ---------------------------------------------------------------------------

# Each entry: ((feature_a, feature_b), combine_fn, weight, midpoint, steepness)
# combine_fn: "product" = a*b, "min" = min(a,b)

FEATURE_INTERACTIONS: dict[str, list[tuple[tuple[str, str], str, float, float, float]]] = {
    "rolling_element_bearing": [
        # Broadband AND periodic = strong bearing signal
        (("spectral_flatness", "periodicity_score"), "product", 0.6, 0.1, 12.0),
        # Mid-band energy AND high mileage = worn bearing
        (("band_mid", "mileage_over_150k"), "product", 0.4, 0.1, 15.0),
    ],
    "gear_mesh_drivetrain": [
        # Harmonic AND speed-dependent = gear mesh
        (("harmonic_ratio", "speed_dependency"), "product", 0.6, 0.15, 12.0),
        # Low-mid band AND harmonic = gear fundamental
        (("band_low_mid", "harmonic_ratio"), "product", 0.4, 0.1, 12.0),
    ],
    "belt_drive_friction": [
        # High centroid AND intermittent = belt squeal
        (("spectral_centroid", "amplitude_variance"), "product", 0.5, 0.005, 15.0),
        # Cold AND RPM dependent = classic belt squeal
        (("cold_only", "rpm_dependency"), "product", 0.5, 0.5, 20.0),
    ],
    "hydraulic_flow_cavitation": [
        # Load-dependent AND mid-band = hydraulic pump
        (("load_dependency", "band_mid"), "product", 0.4, 0.1, 12.0),
    ],
    "electrical_interference": [
        # Tonal AND steady = electrical
        (("harmonic_ratio", "spectral_centroid"), "product", 0.5, 0.05, 12.0),
    ],
    "combustion_impulse": [
        # Impulsive AND periodic = engine firing events
        (("transient_density", "periodicity_score"), "product", 0.7, 0.05, 12.0),
        # High crest AND RPM dependent = combustion knock
        (("crest_factor", "rpm_dependency"), "product", 0.5, 0.1, 15.0),
    ],
    "structural_resonance": [
        # Impulsive AND intermittent = clunk/rattle
        (("transient_density", "intermittent"), "product", 0.5, 0.05, 15.0),
        # Broadband AND localized = structural
        (("spectral_bandwidth", "mechanical_localization"), "product", 0.4, 0.1, 12.0),
    ],
}


# ---------------------------------------------------------------------------
# Constraint Penalties (non-negotiable physics rules)
# ---------------------------------------------------------------------------

# Each entry: (feature_name, operator, threshold, base_penalty, scale)
# operator: "lt", "gt", "eq"
# For proportional penalties:
#   "lt": penalty scales as (threshold - value) / scale
#   "gt": penalty scales as (value - threshold) / scale
#   "eq": full penalty (boolean features)
# scale = 0 means binary (full penalty or nothing)

CONSTRAINT_PENALTIES: dict[str, list[tuple[str, str, float, float, float]]] = {
    "gear_mesh_drivetrain": [
        # Gear mesh cannot be thermal-only
        ("cold_only", "eq", 1.0, 0.6, 0.0),
        # Gear mesh does not occur purely at idle (needs speed)
        ("occurs_at_idle", "eq", 1.0, 0.7, 0.0),
        # Gear mesh must have harmonic content
        ("harmonic_ratio", "lt", 0.2, 0.8, 0.2),
    ],
    "electrical_interference": [
        # Electrical noise is not low-frequency rumble
        ("spectral_centroid", "lt", 0.05, 0.8, 0.05),
        # If user localizes to a mechanical source, unlikely electrical
        ("mechanical_localization", "eq", 1.0, 0.9, 0.0),
        # Electrical is tonal; high flatness argues against
        ("spectral_flatness", "gt", 0.6, 0.6, 0.3),
        # Electrical is not knock or rattle
        ("char_knock_tap", "eq", 1.0, 0.7, 0.0),
        ("char_rattle_buzz", "eq", 1.0, 0.7, 0.0),
    ],
    "rolling_element_bearing": [
        # Bearings don't produce strong harmonics
        ("harmonic_ratio", "gt", 0.7, 0.5, 0.3),
    ],
    "belt_drive_friction": [
        # Belt noise should have some high-frequency content
        ("spectral_centroid", "lt", 0.03, 0.6, 0.03),
        # Belt noise does not sound like knocking
        ("char_knock_tap", "eq", 1.0, 0.7, 0.0),
        # Belt noise does not sound like rattling
        ("char_rattle_buzz", "eq", 1.0, 0.6, 0.0),
        # Belt tracks RPM, not wheel speed
        # Penalize if speed-dependent but NOT rpm-dependent
        # (handled as compound rule in _apply_compound_constraints)
    ],
    "combustion_impulse": [
        # Combustion noise must be RPM-related
        ("rpm_dependency", "eq", 0.0, 0.5, 0.0),
        # Combustion is impulsive; low transient density rules it out
        ("transient_density", "lt", 0.05, 0.6, 0.05),
    ],
    "hydraulic_flow_cavitation": [
        # If purely speed-dependent, it's drivetrain not hydraulic
        ("speed_dependency", "eq", 1.0, 0.4, 0.0),
        # Cavitation is broadband; very low flatness argues against
        ("spectral_flatness", "lt", 0.1, 0.5, 0.1),
    ],
    "structural_resonance": [
        # Structural resonance is not tonal/harmonic
        ("harmonic_ratio", "gt", 0.6, 0.5, 0.3),
        # Structural issues are typically intermittent; constant noise argues against
        # (If user explicitly says NOT intermittent, small penalty)
    ],
}


# ---------------------------------------------------------------------------
# Diagnosis Result
# ---------------------------------------------------------------------------

@dataclass
class DiagnosisResult:
    """Complete output of the diagnostic pipeline."""
    class_scores: dict[str, float]          # Normalized probabilities
    top_class: str                           # Highest scoring class
    confidence: str                          # "high", "medium", "low"
    is_ambiguous: bool                       # True if max score < 0.4
    features: dict                           # All extracted features
    penalties_applied: dict[str, float]      # Total penalty per class
    raw_scores: dict[str, float]             # Pre-normalization scores
    fingerprint_matches: list[MatchResult]   # From DB matching
    fingerprint_count: int                   # Number of fingerprints
    llm_narrative: str | None = None         # Optional LLM explanation


# ---------------------------------------------------------------------------
# Scoring Functions
# ---------------------------------------------------------------------------

def score_mechanical_classes(features: AudioFeatures) -> dict[str, float]:
    """
    Score each mechanical class using sigmoid-scaled feature weights
    plus feature interaction terms.

    Each class starts with a uniform prior (1 / num_classes),
    then sigmoid-scaled feature weights and interaction terms
    are applied additively.

    Args:
        features: Extracted audio + behavioral features.

    Returns:
        Dict mapping class name -> raw score.
    """
    feature_dict = features.to_dict()
    n_classes = len(MECHANICAL_CLASSES)
    base_prior = 1.0 / n_classes

    scores = {}
    for cls in MECHANICAL_CLASSES:
        score = base_prior
        score += _apply_sigmoid_weights(cls, feature_dict)
        score += _apply_interaction_terms(cls, feature_dict)
        scores[cls] = score

    return scores


def _apply_sigmoid_weights(cls: str, features: dict) -> float:
    """
    Apply sigmoid-scaled feature weights for a given class.

    Each weight entry is (feature_name, weight, midpoint, steepness).
    The raw feature value is passed through sigmoid(value, midpoint, steepness)
    then multiplied by the weight.
    """
    weight_sum = 0.0

    weights = FEATURE_WEIGHTS.get(cls, [])
    for feature_name, weight, midpoint, steepness in weights:
        value = features.get(feature_name, 0.0)
        scaled = sigmoid_scale(value, midpoint, steepness)
        weight_sum += scaled * weight

    return weight_sum


def _apply_interaction_terms(cls: str, features: dict) -> float:
    """
    Apply feature interaction (cross-feature) terms for a given class.

    Each interaction is ((feature_a, feature_b), combine_fn, weight, mid, steep).
    """
    total = 0.0

    interactions = FEATURE_INTERACTIONS.get(cls, [])
    for (feat_a, feat_b), combine_fn, weight, midpoint, steepness in interactions:
        val_a = features.get(feat_a, 0.0)
        val_b = features.get(feat_b, 0.0)

        if combine_fn == "product":
            combined = val_a * val_b
        elif combine_fn == "min":
            combined = min(val_a, val_b)
        else:
            combined = val_a * val_b

        scaled = sigmoid_scale(combined, midpoint, steepness)
        total += scaled * weight

    return total


def apply_constraint_penalties(
    scores: dict[str, float],
    features: AudioFeatures,
) -> tuple[dict[str, float], dict[str, float]]:
    """
    Apply proportional physics constraint penalties to raw scores.

    Proportional: penalty scales with how far past the threshold
    the feature value is. Binary (eq) constraints apply full penalty.

    Args:
        scores: Raw class scores.
        features: Extracted features.

    Returns:
        Tuple of (penalized_scores, penalties_applied).
    """
    feature_dict = features.to_dict()
    penalized = dict(scores)
    penalties = {cls: 0.0 for cls in MECHANICAL_CLASSES}

    for cls in MECHANICAL_CLASSES:
        constraints = CONSTRAINT_PENALTIES.get(cls, [])
        total_penalty = 0.0

        for feature_name, operator, threshold, base_penalty, scale in constraints:
            value = feature_dict.get(feature_name, 0.0)
            penalty_amount = _compute_proportional_penalty(
                value, operator, threshold, base_penalty, scale
            )
            total_penalty += penalty_amount

        # Apply compound constraints (multi-feature rules)
        total_penalty += _apply_compound_constraints(cls, feature_dict)

        penalized[cls] -= total_penalty
        if penalized[cls] < 0:
            penalized[cls] = 0.0

        penalties[cls] = total_penalty

    return penalized, penalties


def _compute_proportional_penalty(
    value: float,
    operator: str,
    threshold: float,
    base_penalty: float,
    scale: float,
) -> float:
    """
    Compute a proportional penalty based on how far past threshold.

    If scale == 0, uses binary (full penalty if condition met, else 0).
    If scale > 0, penalty scales linearly with violation distance,
    capped at base_penalty.
    """
    if operator == "eq":
        # Boolean equality: full penalty or nothing
        if abs(value - threshold) < 0.01:
            return base_penalty
        return 0.0

    if operator == "lt":
        if value >= threshold:
            return 0.0  # No violation
        if scale <= 0:
            return base_penalty  # Binary
        distance = threshold - value
        return base_penalty * min(distance / scale, 1.0)

    if operator == "gt":
        if value <= threshold:
            return 0.0  # No violation
        if scale <= 0:
            return base_penalty  # Binary
        distance = value - threshold
        return base_penalty * min(distance / scale, 1.0)

    return 0.0


def _apply_compound_constraints(cls: str, features: dict) -> float:
    """
    Apply multi-feature compound constraints that can't be expressed
    as single-feature rules.
    """
    penalty = 0.0

    if cls == "belt_drive_friction":
        # Belt tracks RPM, not wheel speed.
        # Penalize if speed-dependent but NOT rpm-dependent
        speed = features.get("speed_dependency", 0.0)
        rpm = features.get("rpm_dependency", 0.0)
        if speed > 0.5 and rpm < 0.5:
            penalty += 0.5

    return penalty


def normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    """
    Normalize scores to sum to 1.0 (probability distribution).

    If all scores are zero, returns uniform zeros.
    """
    total = sum(scores.values())

    if total <= 0:
        return {cls: 0.0 for cls in scores}

    return {cls: score / total for cls, score in scores.items()}


def check_failure_safety(
    normalized_scores: dict[str, float],
    threshold: float = 0.4,
    margin_threshold: float = 0.1,
) -> tuple[bool, str]:
    """
    Check if the top score exceeds the confidence threshold AND
    has sufficient margin over the second-place class.

    A score of 0.45 with #2 at 0.43 is ambiguous (margin too small).
    A score of 0.45 with #2 at 0.20 is medium confidence.

    Returns:
        Tuple of (is_ambiguous, confidence_level).
    """
    if not normalized_scores:
        return True, "low"

    sorted_scores = sorted(normalized_scores.values(), reverse=True)
    max_score = sorted_scores[0]
    second_score = sorted_scores[1] if len(sorted_scores) > 1 else 0.0
    margin = max_score - second_score

    if max_score < threshold:
        return True, "low"

    if margin < margin_threshold:
        # Top two classes are too close together
        return True, "low"

    if max_score >= 0.6 and margin >= 0.2:
        return False, "high"
    else:
        return False, "medium"


# ---------------------------------------------------------------------------
# Full Pipeline Orchestrator
# ---------------------------------------------------------------------------

def run_diagnostic_pipeline(
    audio_data: np.ndarray,
    sr: int,
    context: BehavioralContext,
    user_codes: list[str],
    db_manager: DatabaseManager,
    llm_enabled: bool = False,
    progress_callback=None,
) -> DiagnosisResult:
    """
    Run the complete diagnostic pipeline.

    Steps:
    1. Preprocess audio
    2. Extract features (spectral + temporal + sub-band + behavioral)
    3. Generate fingerprints + DB match
    4. Score mechanical classes (sigmoid + interactions + negative evidence)
    5. Apply proportional constraint penalties
    6. Normalize scores
    7. Failure safety check (threshold + margin)
    8. Optional LLM reasoning
    9. Merge and return DiagnosisResult

    Args:
        audio_data: Raw mono float32 audio.
        sr: Sample rate.
        context: User behavioral observations.
        user_codes: User-entered trouble codes.
        db_manager: Database manager for fingerprint matching.
        llm_enabled: Whether to invoke LLM reasoning.
        progress_callback: Optional callable(str) for progress updates.

    Returns:
        DiagnosisResult with all analysis data.
    """
    def _progress(msg: str):
        if progress_callback:
            progress_callback(msg)

    # Step 1: Preprocess
    _progress("Preprocessing audio...")
    conditioned = preprocess_audio(audio_data, sr)

    # Step 2: Extract features
    _progress("Extracting features...")
    features = extract_features(conditioned, sr, context)

    # Step 3: Fingerprint + DB match
    _progress("Generating fingerprints...")
    fingerprints = generate_fingerprint(conditioned, sr)
    fp_count = len(fingerprints)

    _progress(f"Matching {fp_count} fingerprints against database...")
    fp_matches = match_with_trouble_codes(
        fingerprints, db_manager, user_codes
    )

    # Step 4: Score mechanical classes
    _progress("Scoring mechanical classes...")
    raw_scores = score_mechanical_classes(features)

    # Step 4.5: Apply trouble code evidence boosts
    if user_codes:
        _progress("Applying trouble code evidence boosts...")
        try:
            from database.trouble_code_lookup import get_mechanical_class_boosts
            code_boosts = get_mechanical_class_boosts(user_codes, db_manager)
            for cls, boost in code_boosts.items():
                if cls in raw_scores:
                    raw_scores[cls] += boost
        except Exception:
            pass  # Table may not exist yet; gracefully skip

    # Step 5: Apply constraint penalties
    _progress("Applying physics constraints...")
    penalized_scores, penalties = apply_constraint_penalties(
        raw_scores, features
    )

    # Step 6: Normalize
    normalized_scores = normalize_scores(penalized_scores)

    # Step 7: Failure safety
    is_ambiguous, confidence = check_failure_safety(normalized_scores)

    # Determine top class
    if normalized_scores and max(normalized_scores.values()) > 0:
        top_class = max(normalized_scores, key=normalized_scores.get)
    else:
        top_class = "unknown"

    # Step 8: Optional LLM reasoning
    llm_narrative = None
    if llm_enabled and not is_ambiguous:
        _progress("Running LLM reasoning...")
        try:
            from core.llm_reasoning import run_llm_reasoning
            llm_narrative = run_llm_reasoning(
                normalized_scores, features, penalties
            )
        except Exception:
            llm_narrative = None

    _progress("Analysis complete.")

    # Step 9: Build result
    return DiagnosisResult(
        class_scores=normalized_scores,
        top_class=top_class,
        confidence=confidence,
        is_ambiguous=is_ambiguous,
        features=features.to_dict(),
        penalties_applied=penalties,
        raw_scores=raw_scores,
        fingerprint_matches=fp_matches,
        fingerprint_count=fp_count,
        llm_narrative=llm_narrative,
    )


# =========================================================================
# TEXT-ONLY (Symptom-First) Diagnostic Pipeline
# =========================================================================
# When the user provides symptoms, trouble codes, and behavioral context
# but no audio recording, we can still produce a high-confidence diagnosis.
# The key idea: multiple independent corroborating signals converging on
# the same class produce reliability comparable to audio analysis.
# =========================================================================

# ---------------------------------------------------------------------------
# Symptom-hint scoring
# ---------------------------------------------------------------------------

def score_from_class_hints(
    class_hints: dict[str, float],
    boost_weight: float = 1.5,
) -> dict[str, float]:
    """
    Convert symptom parser class_hints into additive score contributions.

    class_hints maps mechanical class -> weight (0.0--1.0) from keyword
    matching (e.g. "wheel bearing" -> rolling_element_bearing: 0.8).

    The boost_weight amplifies these into the same scale as FEATURE_WEIGHTS
    contributions.  A hint of 0.8 at boost_weight=1.5 adds 1.2 to raw score.
    """
    scores = {cls: 0.0 for cls in MECHANICAL_CLASSES}
    for cls, weight in class_hints.items():
        if cls in scores:
            scores[cls] += weight * boost_weight
    return scores


# ---------------------------------------------------------------------------
# Signal agreement bonus
# ---------------------------------------------------------------------------

def score_signal_agreement(
    behavioral_scores: dict[str, float],
    hint_scores: dict[str, float],
    code_boosts: dict[str, float],
) -> dict[str, float]:
    """
    Award a convergence bonus when multiple *independent* signal sources
    agree on the same class.

    Sources:
    1. behavioral_scores -- from FEATURE_WEIGHTS applied to behavioral context
    2. hint_scores       -- from symptom parser class_hints
    3. code_boosts       -- from trouble code -> mechanical class mapping

    When 2/3 sources are positive for the same class: +0.3
    When 3/3 sources are positive:                     +0.7

    This is what makes text-only diagnoses "dang near close to certain" --
    independent corroboration drives confidence way up.
    """
    bonus = {cls: 0.0 for cls in MECHANICAL_CLASSES}

    for cls in MECHANICAL_CLASSES:
        sources_positive = 0
        if behavioral_scores.get(cls, 0.0) > 0.1:
            sources_positive += 1
        if hint_scores.get(cls, 0.0) > 0.05:
            sources_positive += 1
        if code_boosts.get(cls, 0.0) > 0.0:
            sources_positive += 1

        if sources_positive >= 3:
            bonus[cls] = 0.7
        elif sources_positive >= 2:
            bonus[cls] = 0.3

    return bonus


# ---------------------------------------------------------------------------
# Text-only constraint penalties
# ---------------------------------------------------------------------------

# Constraints that depend ONLY on behavioral features (no audio needed).
# These are a subset of CONSTRAINT_PENALTIES, keeping only rules that
# reference behavioral features, not spectral/temporal ones.

TEXT_ONLY_CONSTRAINTS: dict[str, list[tuple[str, str, float, float, float]]] = {
    "gear_mesh_drivetrain": [
        # Gear mesh cannot be thermal-only
        ("cold_only", "eq", 1.0, 0.6, 0.0),
        # Gear mesh does not occur purely at idle (needs speed)
        ("occurs_at_idle", "eq", 1.0, 0.7, 0.0),
        # Gear noise is not knock
        ("char_knock_tap", "eq", 1.0, 0.5, 0.0),
        # Gear noise is not squeal
        ("char_squeal", "eq", 1.0, 0.5, 0.0),
        # Gear noise is not rattle
        ("char_rattle_buzz", "eq", 1.0, 0.4, 0.0),
    ],
    "electrical_interference": [
        # If user localizes to a mechanical source, unlikely electrical
        ("mechanical_localization", "eq", 1.0, 0.9, 0.0),
        # Electrical is not knock or rattle
        ("char_knock_tap", "eq", 1.0, 0.7, 0.0),
        ("char_rattle_buzz", "eq", 1.0, 0.7, 0.0),
        ("char_grind_scrape", "eq", 1.0, 0.6, 0.0),
    ],
    "belt_drive_friction": [
        # Belt noise does not sound like knocking
        ("char_knock_tap", "eq", 1.0, 0.7, 0.0),
        # Belt noise does not sound like rattling
        ("char_rattle_buzz", "eq", 1.0, 0.6, 0.0),
        # Belt noise should not be speed-dependent without rpm dependency
        # (compound handled below)
    ],
    "combustion_impulse": [
        # Combustion noise must be RPM-related (unless user didn't specify)
        # Only penalize if user explicitly says speed-dependent but NOT rpm
        ("char_whine", "eq", 1.0, 0.5, 0.0),
        ("char_squeal", "eq", 1.0, 0.5, 0.0),
        ("char_hiss", "eq", 1.0, 0.4, 0.0),
    ],
    "hydraulic_flow_cavitation": [
        # If purely speed-dependent, it's drivetrain not hydraulic
        ("speed_dependency", "eq", 1.0, 0.4, 0.0),
        # Hydraulic is not knock or rattle
        ("char_knock_tap", "eq", 1.0, 0.5, 0.0),
        ("char_rattle_buzz", "eq", 1.0, 0.4, 0.0),
        ("char_squeal", "eq", 1.0, 0.4, 0.0),
    ],
    "rolling_element_bearing": [
        # Bearings don't squeal
        ("char_squeal", "eq", 1.0, 0.4, 0.0),
        # Bearings don't knock
        ("char_knock_tap", "eq", 1.0, 0.4, 0.0),
    ],
    "structural_resonance": [
        # Structural is not whine
        ("char_whine", "eq", 1.0, 0.5, 0.0),
        # Structural is not squeal
        ("char_squeal", "eq", 1.0, 0.5, 0.0),
        # Structural is not hiss
        ("char_hiss", "eq", 1.0, 0.5, 0.0),
    ],
}


def apply_text_only_constraints(
    scores: dict[str, float],
    features: AudioFeatures,
) -> tuple[dict[str, float], dict[str, float]]:
    """
    Apply behavioral-only constraint penalties (no audio-dependent rules).
    Same logic as apply_constraint_penalties but uses TEXT_ONLY_CONSTRAINTS.
    """
    feature_dict = features.to_dict()
    penalized = dict(scores)
    penalties = {cls: 0.0 for cls in MECHANICAL_CLASSES}

    for cls in MECHANICAL_CLASSES:
        constraints = TEXT_ONLY_CONSTRAINTS.get(cls, [])
        total_penalty = 0.0

        for feature_name, operator, threshold, base_penalty, scale in constraints:
            value = feature_dict.get(feature_name, 0.0)
            penalty_amount = _compute_proportional_penalty(
                value, operator, threshold, base_penalty, scale
            )
            total_penalty += penalty_amount

        # Compound: belt shouldn't be speed-dependent without RPM
        total_penalty += _apply_compound_constraints(cls, feature_dict)

        penalized[cls] -= total_penalty
        if penalized[cls] < 0:
            penalized[cls] = 0.0
        penalties[cls] = total_penalty

    return penalized, penalties


# ---------------------------------------------------------------------------
# Data sufficiency & confidence for text-only
# ---------------------------------------------------------------------------

def compute_data_sufficiency(
    context: BehavioralContext,
    class_hints: dict[str, float],
    user_codes: list[str],
    symptom_confidence: float,
) -> float:
    """
    Score how much diagnostic data the user has provided (0.0--1.0).
    More data = higher potential confidence ceiling.

    Tracks 8 independent data categories:
    1. Noise character described
    2. Operating condition (RPM/speed/load/idle)
    3. Environmental condition (cold/intermittent)
    4. Location hint
    5. Vehicle info (type or mileage)
    6. Duration info
    7. Trouble codes provided
    8. Direct component mentions (class hints)
    """
    score = 0.0

    # 1. Noise character
    if context.noise_character != "unknown":
        score += 0.15

    # 2. Operating condition
    has_operating = any([
        context.rpm_dependency,
        context.speed_dependency,
        context.load_dependency,
        context.occurs_at_idle,
    ])
    if has_operating:
        score += 0.15

    # 3. Environmental condition
    has_env = any([context.cold_only, context.intermittent])
    if has_env:
        score += 0.10

    # 4. Location / localization
    if context.mechanical_localization:
        score += 0.10

    # 5. Vehicle info
    has_vehicle = context.vehicle_type != "unknown" or context.mileage_range != "unknown"
    if has_vehicle:
        score += 0.10

    # 6. Duration
    if context.issue_duration != "unknown":
        score += 0.05

    # 7. Trouble codes
    if user_codes:
        score += 0.15
        if len(user_codes) >= 2:
            score += 0.05  # Multiple codes = more data

    # 8. Direct component mentions
    if class_hints and max(class_hints.values(), default=0) > 0.3:
        score += 0.15

    return min(1.0, score)


def check_text_only_confidence(
    normalized_scores: dict[str, float],
    data_sufficiency: float,
    n_agreeing_sources: int,
) -> tuple[bool, str]:
    """
    Confidence calibration for text-only diagnosis.

    Unlike audio+text which uses fixed thresholds, text-only confidence
    scales with data sufficiency and signal agreement.

    Rules:
    - HIGH: top score >= 0.35 AND margin >= 0.10 AND sufficiency >= 0.5
            AND 2+ agreeing sources
    - MEDIUM: top score >= 0.25 AND margin >= 0.05 AND sufficiency >= 0.3
    - LOW (ambiguous): anything else

    The thresholds are deliberately lower than audio mode because
    normalized behavioral scores have a different distribution.
    """
    if not normalized_scores:
        return True, "low"

    sorted_scores = sorted(normalized_scores.values(), reverse=True)
    top = sorted_scores[0]
    second = sorted_scores[1] if len(sorted_scores) > 1 else 0.0
    margin = top - second

    # High confidence: clear winner + good data + agreement
    if (top >= 0.35 and margin >= 0.10
            and data_sufficiency >= 0.5 and n_agreeing_sources >= 2):
        return False, "high"

    # Medium confidence: reasonable winner + some data
    if top >= 0.25 and margin >= 0.05 and data_sufficiency >= 0.3:
        return False, "medium"

    return True, "low"


# ---------------------------------------------------------------------------
# Text-Only Pipeline Orchestrator
# ---------------------------------------------------------------------------

def run_text_diagnostic_pipeline(
    context: BehavioralContext,
    class_hints: dict[str, float],
    user_codes: list[str],
    db_manager: DatabaseManager,
    symptom_confidence: float = 0.0,
    llm_enabled: bool = False,
    progress_callback=None,
) -> DiagnosisResult:
    """
    Run the diagnostic pipeline using ONLY text-based inputs (no audio).

    This is the primary diagnostic pathway.  Audio is optional enhancement.

    Steps:
    1. Build features from behavioral context (no spectral/temporal)
    2. Score mechanical classes from behavioral features
    3. Add symptom parser class_hint scores
    4. Add trouble code boosts
    5. Compute signal agreement bonus
    6. Apply behavioral-only constraint penalties
    7. Normalize scores
    8. Compute data sufficiency & calibrate confidence
    9. Optional LLM reasoning
    10. Build DiagnosisResult

    Args:
        context: User behavioral observations (from GUI + symptom parser).
        class_hints: Symptom parser's direct class hints (class -> weight).
        user_codes: User-entered OBD-II trouble codes.
        db_manager: Database manager for code lookups.
        symptom_confidence: The symptom parser's parse confidence (0--1).
        llm_enabled: Whether to invoke LLM reasoning.
        progress_callback: Optional callable(str) for progress updates.

    Returns:
        DiagnosisResult with all analysis data.
    """
    def _progress(msg: str):
        if progress_callback:
            progress_callback(msg)

    # Step 1: Build features from behavioral context only
    _progress("Building features from symptoms...")
    features = extract_features_from_context(context)

    # Step 2: Score from behavioral features (uses existing FEATURE_WEIGHTS)
    _progress("Scoring from behavioral context...")
    behavioral_scores = score_mechanical_classes(features)

    # Step 3: Score from symptom parser class hints
    _progress("Applying symptom analysis...")
    hint_scores = score_from_class_hints(class_hints or {})

    # Step 4: Trouble code boosts
    code_boosts = {cls: 0.0 for cls in MECHANICAL_CLASSES}
    if user_codes:
        _progress("Applying trouble code evidence...")
        try:
            from database.trouble_code_lookup import get_mechanical_class_boosts
            code_boosts = get_mechanical_class_boosts(user_codes, db_manager)
        except Exception:
            pass

    # Step 5: Signal agreement bonus
    _progress("Computing signal agreement...")
    agreement_bonus = score_signal_agreement(
        behavioral_scores, hint_scores, code_boosts
    )

    # Count agreeing sources for confidence calibration
    n_agreeing = 0
    if class_hints:
        top_hint_cls = max(class_hints, key=class_hints.get) if class_hints else None
    else:
        top_hint_cls = None

    if top_hint_cls:
        n = 0
        if behavioral_scores.get(top_hint_cls, 0) > 0.2:
            n += 1
        if hint_scores.get(top_hint_cls, 0) > 0.05:
            n += 1
        if code_boosts.get(top_hint_cls, 0) > 0:
            n += 1
        n_agreeing = n

    # Combine all score contributions
    raw_scores = {}
    for cls in MECHANICAL_CLASSES:
        raw_scores[cls] = (
            behavioral_scores[cls]
            + hint_scores.get(cls, 0.0)
            + code_boosts.get(cls, 0.0)
            + agreement_bonus.get(cls, 0.0)
        )

    # Step 6: Apply text-only constraint penalties
    _progress("Applying behavioral constraints...")
    penalized_scores, penalties = apply_text_only_constraints(raw_scores, features)

    # Step 7: Normalize
    normalized_scores = normalize_scores(penalized_scores)

    # Step 8: Data sufficiency & confidence
    _progress("Calibrating confidence...")
    sufficiency = compute_data_sufficiency(
        context, class_hints or {}, user_codes, symptom_confidence
    )
    is_ambiguous, confidence = check_text_only_confidence(
        normalized_scores, sufficiency, n_agreeing
    )

    # Determine top class
    if normalized_scores and max(normalized_scores.values()) > 0:
        top_class = max(normalized_scores, key=normalized_scores.get)
    else:
        top_class = "unknown"

    # Step 9: Optional LLM reasoning
    llm_narrative = None
    if llm_enabled and not is_ambiguous:
        _progress("Running LLM reasoning...")
        try:
            from core.llm_reasoning import run_llm_reasoning
            llm_narrative = run_llm_reasoning(
                normalized_scores, features, penalties
            )
        except Exception:
            llm_narrative = None

    _progress("Diagnosis complete.")

    # Step 10: Build result
    return DiagnosisResult(
        class_scores=normalized_scores,
        top_class=top_class,
        confidence=confidence,
        is_ambiguous=is_ambiguous,
        features=features.to_dict(),
        penalties_applied=penalties,
        raw_scores=raw_scores,
        fingerprint_matches=[],   # No fingerprints in text-only mode
        fingerprint_count=0,
        llm_narrative=llm_narrative,
    )


# ---------------------------------------------------------------------------
# Unified Pipeline Router
# ---------------------------------------------------------------------------

def run_diagnostic_pipeline_auto(
    audio_data: np.ndarray | None,
    sr: int,
    context: BehavioralContext,
    class_hints: dict[str, float],
    user_codes: list[str],
    db_manager: DatabaseManager,
    symptom_confidence: float = 0.0,
    llm_enabled: bool = False,
    progress_callback=None,
) -> DiagnosisResult:
    """
    Automatically route to the audio or text-only pipeline based on input.

    If audio_data is provided: runs the full audio+text pipeline
    (enriched with class hints and code boosts).

    If audio_data is None: runs the text-only pipeline.

    This is the recommended entry point.
    """
    if audio_data is not None and len(audio_data) > 0:
        # Full audio pipeline (also fold in class hints post-scoring)
        def _progress(msg):
            if progress_callback:
                progress_callback(msg)

        result = run_diagnostic_pipeline(
            audio_data=audio_data,
            sr=sr,
            context=context,
            user_codes=user_codes,
            db_manager=db_manager,
            llm_enabled=llm_enabled,
            progress_callback=progress_callback,
        )

        # Enrich audio result with class hint boosts if available
        if class_hints:
            hint_bonus = score_from_class_hints(class_hints, boost_weight=0.5)
            enriched_raw = {}
            for cls in MECHANICAL_CLASSES:
                enriched_raw[cls] = result.raw_scores.get(cls, 0.0) + hint_bonus.get(cls, 0.0)

            # Re-apply constraints with enriched scores
            features_obj = extract_features_from_context(context)
            penalized, penalties = apply_constraint_penalties(
                enriched_raw, features_obj
            )
            normalized = normalize_scores(penalized)
            is_ambiguous, confidence = check_failure_safety(normalized)

            top_class = max(normalized, key=normalized.get) if normalized else "unknown"

            return DiagnosisResult(
                class_scores=normalized,
                top_class=top_class,
                confidence=confidence,
                is_ambiguous=is_ambiguous,
                features=result.features,
                penalties_applied=penalties,
                raw_scores=enriched_raw,
                fingerprint_matches=result.fingerprint_matches,
                fingerprint_count=result.fingerprint_count,
                llm_narrative=result.llm_narrative,
            )

        return result
    else:
        # Text-only pipeline
        return run_text_diagnostic_pipeline(
            context=context,
            class_hints=class_hints,
            user_codes=user_codes,
            db_manager=db_manager,
            symptom_confidence=symptom_confidence,
            llm_enabled=llm_enabled,
            progress_callback=progress_callback,
        )
