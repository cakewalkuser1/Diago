"""
Symptom Parser (Tier 1 -- Keyword-Based)
Extracts structured diagnostic context from free-text symptom descriptions.

The parser converts natural language like:
    "My car makes a whining noise at high speed, gets louder when I turn"
into a BehavioralContext object + matched keywords + suggested trouble codes.

Architecture:
- Multi-word phrase matching (longest match first) to avoid partial hits
- Case-insensitive, punctuation-tolerant tokenization
- Maps keywords -> BehavioralContext fields + mechanical class hints
- Confidence score based on keyword coverage density
- Suggested OBD-II codes based on matched symptom patterns

This module requires NO external dependencies (no LLM, no ML).
"""

import re
from dataclasses import dataclass, field
from core.feature_extraction import BehavioralContext


# ---------------------------------------------------------------------------
# ParsedSymptoms output
# ---------------------------------------------------------------------------

@dataclass
class ParsedSymptoms:
    """Result of parsing a user's symptom description."""
    # The auto-filled behavioral context from keywords
    context: BehavioralContext = field(default_factory=BehavioralContext)
    # All keywords that were matched in the text
    matched_keywords: list[str] = field(default_factory=list)
    # Confidence in the parse (0.0 - 1.0 based on keyword density)
    confidence: float = 0.0
    # Suggested OBD-II codes based on symptom patterns
    suggested_codes: list[str] = field(default_factory=list)
    # Hints about where the noise is coming from
    location_hints: list[str] = field(default_factory=list)
    # Mechanical class hints extracted from keywords
    class_hints: dict[str, float] = field(default_factory=dict)
    # Original text that was parsed
    original_text: str = ""


# ---------------------------------------------------------------------------
# Keyword Dictionary (~200+ entries)
# Maps phrase -> list of (field, value) pairs to set on BehavioralContext
# Organized by category for maintainability
# ---------------------------------------------------------------------------

# noise_character keywords
_NOISE_CHARACTER_KEYWORDS: dict[str, str] = {
    # whine
    "whine": "whine", "whining": "whine", "high pitched whine": "whine",
    "electrical whine": "whine", "power steering whine": "whine",
    "alternator whine": "whine", "transmission whine": "whine",
    "differential whine": "whine",
    # squeal
    "squeal": "squeal", "squealing": "squeal", "squeaks": "squeal",
    "squeaky": "squeal", "screeching": "squeal", "screech": "squeal",
    "high pitched squeal": "squeal", "belt squeal": "squeal",
    "brake squeal": "squeal",
    # knock / tap
    "knock": "knock_tap", "knocking": "knock_tap", "tap": "knock_tap",
    "tapping": "knock_tap", "tick": "knock_tap", "ticking": "knock_tap",
    "ping": "knock_tap", "pinging": "knock_tap", "detonation": "knock_tap",
    "rod knock": "knock_tap", "engine knock": "knock_tap",
    "lifter tick": "knock_tap", "piston slap": "knock_tap",
    "injector tick": "knock_tap",
    # rattle / buzz
    "rattle": "rattle_buzz", "rattling": "rattle_buzz",
    "buzz": "rattle_buzz", "buzzing": "rattle_buzz",
    "vibration": "rattle_buzz", "vibrating": "rattle_buzz",
    "loose heat shield": "rattle_buzz", "exhaust rattle": "rattle_buzz",
    "catalytic converter rattle": "rattle_buzz",
    "timing chain rattle": "rattle_buzz",
    # hum / drone
    "hum": "hum_drone", "humming": "hum_drone", "drone": "hum_drone",
    "droning": "hum_drone", "low rumble": "hum_drone",
    "road noise": "hum_drone", "wheel bearing hum": "hum_drone",
    "growl": "hum_drone", "growling": "hum_drone", "rumble": "hum_drone",
    # click / tick
    "click": "click_tick", "clicking": "click_tick", "pop": "click_tick",
    "popping": "click_tick", "snap": "click_tick", "snapping": "click_tick",
    "cv joint click": "click_tick", "relay click": "click_tick",
    "blend door click": "click_tick",
    # grind / scrape
    "grind": "grind_scrape", "grinding": "grind_scrape",
    "scrape": "grind_scrape", "scraping": "grind_scrape",
    "metal on metal": "grind_scrape", "brake grinding": "grind_scrape",
    "starter grind": "grind_scrape",
    # hiss
    "hiss": "hiss", "hissing": "hiss", "air leak": "hiss",
    "vacuum leak": "hiss", "boost leak": "hiss",
    "exhaust leak hiss": "hiss",
}

# RPM / speed / load dependency keywords
_RPM_KEYWORDS = [
    "when revving", "with rpm", "at high rpm", "at low rpm",
    "when accelerating", "under acceleration", "when i rev",
    "rpm dependent", "increases with rpm", "gets louder revving",
    "proportional to engine speed", "varies with rpm",
    "worse when revving", "louder at higher rpm",
]

_SPEED_KEYWORDS = [
    "at high speed", "at highway speed", "at speed", "at 60 mph",
    "at 70 mph", "faster i go", "speed dependent",
    "increases with speed", "increases with vehicle speed",
    "when driving fast", "with speed",
    "gets louder with speed", "proportional to speed",
    "proportional to vehicle speed",
    "worse at highway speed", "only at high speed",
    "on the highway", "on the freeway",
    "varies with speed", "changes with speed",
]

_LOAD_KEYWORDS = [
    "under load", "when towing", "going uphill",
    "when pulling", "under heavy load", "when carrying weight",
    "with load", "hills", "uphill", "steep grade",
    "worse under load",
]

_COLD_KEYWORDS = [
    "at cold start", "when cold", "cold engine", "cold morning",
    "first start of the day", "goes away when warm",
    "only when cold", "before warm up", "cold startup",
    "winter", "freezing", "sub zero",
    "engine is cold", "is cold", "while cold", "car is cold",
    "not warmed up", "before warming up",
]

_IDLE_KEYWORDS = [
    "at idle", "idling", "when sitting still", "in park",
    "at a stop light", "at stop", "standing still",
    "when stopped", "at rest", "not moving", "in neutral",
    "rough idle", "idle fluctuates",
]

# Perceived frequency keywords
_FREQ_LOW_KEYWORDS = [
    "low pitched", "low frequency", "bass", "deep sound",
    "low tone", "deep rumble", "low growl", "bassy",
]

_FREQ_MID_KEYWORDS = [
    "mid range", "mid pitched", "medium pitch", "moderate pitch",
]

_FREQ_HIGH_KEYWORDS = [
    "high pitched", "high frequency", "shrill", "piercing",
    "high tone", "treble", "sharp sound", "ear piercing",
]

# Intermittent keywords
_INTERMITTENT_KEYWORDS = [
    "comes and goes", "intermittent", "on and off",
    "sometimes", "occasionally", "not all the time",
    "random", "sporadic", "every now and then",
    "once in a while", "not constant", "goes away",
]

# Issue duration keywords
_DURATION_MAP: dict[str, str] = {
    "just started": "just_started", "started today": "just_started",
    "new noise": "just_started", "started this morning": "just_started",
    "since yesterday": "just_started",
    "few days": "days", "couple days": "days",
    "started this week": "days", "for a few days": "days",
    "past few weeks": "weeks", "couple weeks": "weeks",
    "for weeks": "weeks", "started last week": "weeks",
    "for a week": "weeks",
    "for months": "months", "few months": "months",
    "been going on for a while": "months", "long time": "months",
    "several months": "months", "since last year": "months",
}

# Vehicle type keywords
_VEHICLE_TYPE_MAP: dict[str, str] = {
    "sedan": "sedan", "car": "sedan", "coupe": "sedan",
    "truck": "suv_truck", "suv": "suv_truck", "pickup": "suv_truck",
    "van": "suv_truck", "crossover": "suv_truck", "jeep": "suv_truck",
    "sports car": "sports", "sporty": "sports", "turbo": "sports",
    "performance": "sports",
    "diesel": "diesel", "tdi": "diesel", "duramax": "diesel",
    "powerstroke": "diesel", "cummins": "diesel",
    "hybrid": "hybrid_ev", "electric": "hybrid_ev",
    "ev": "hybrid_ev", "prius": "hybrid_ev", "tesla": "hybrid_ev",
}

# Location hints (where the noise comes from)
_LOCATION_KEYWORDS: dict[str, str] = {
    "front": "front", "front end": "front", "front of car": "front",
    "front left": "front_left", "front right": "front_right",
    "driver side front": "front_left", "passenger side front": "front_right",
    "rear": "rear", "back": "rear", "back of car": "rear",
    "rear left": "rear_left", "rear right": "rear_right",
    "driver side": "left", "passenger side": "right",
    "left side": "left", "right side": "right",
    "under the hood": "engine_bay", "engine bay": "engine_bay",
    "engine compartment": "engine_bay",
    "under the car": "undercarriage", "underneath": "undercarriage",
    "exhaust": "exhaust", "tailpipe": "exhaust",
    "dashboard": "dashboard", "behind the dash": "dashboard",
    "wheel": "wheel_area", "tire area": "wheel_area",
    "transmission": "transmission_area", "trans": "transmission_area",
    "steering wheel": "steering",
    "cabin": "cabin", "inside the car": "cabin",
}

# Mechanical class hint keywords (maps to our 7 classes + weight)
_CLASS_HINT_KEYWORDS: dict[str, list[tuple[str, float]]] = {
    # bearing indicators
    "bearing": [("rolling_element_bearing", 0.6)],
    "wheel bearing": [("rolling_element_bearing", 0.8)],
    "idler pulley": [("rolling_element_bearing", 0.7)],
    "water pump": [("rolling_element_bearing", 0.5)],
    "alternator bearing": [("rolling_element_bearing", 0.7)],
    "ac compressor bearing": [("rolling_element_bearing", 0.6)],
    # gear/drivetrain indicators
    "transmission": [("gear_mesh_drivetrain", 0.5)],
    "gear": [("gear_mesh_drivetrain", 0.5)],
    "differential": [("gear_mesh_drivetrain", 0.6)],
    "transfer case": [("gear_mesh_drivetrain", 0.6)],
    "driveshaft": [("gear_mesh_drivetrain", 0.5)],
    "u joint": [("gear_mesh_drivetrain", 0.5)],
    "cv joint": [("gear_mesh_drivetrain", 0.4)],
    "axle": [("gear_mesh_drivetrain", 0.4)],
    "torque converter": [("gear_mesh_drivetrain", 0.6)],
    # belt/friction indicators
    "belt": [("belt_drive_friction", 0.6)],
    "serpentine belt": [("belt_drive_friction", 0.8)],
    "belt tensioner": [("belt_drive_friction", 0.7)],
    "timing belt": [("belt_drive_friction", 0.5)],
    "drive belt": [("belt_drive_friction", 0.7)],
    "clutch": [("belt_drive_friction", 0.4)],
    "brake pad": [("belt_drive_friction", 0.4)],
    "brake": [("belt_drive_friction", 0.3)],
    # hydraulic indicators
    "power steering": [("hydraulic_flow_cavitation", 0.7)],
    "power steering pump": [("hydraulic_flow_cavitation", 0.8)],
    "hydraulic": [("hydraulic_flow_cavitation", 0.6)],
    "coolant": [("hydraulic_flow_cavitation", 0.3)],
    "fuel pump": [("hydraulic_flow_cavitation", 0.5)],
    "abs pump": [("hydraulic_flow_cavitation", 0.5)],
    # electrical indicators
    "electrical": [("electrical_interference", 0.5)],
    "alternator": [("electrical_interference", 0.4), ("rolling_element_bearing", 0.3)],
    "starter": [("electrical_interference", 0.4)],
    "relay": [("electrical_interference", 0.5)],
    "fuse": [("electrical_interference", 0.3)],
    "battery": [("electrical_interference", 0.3)],
    # combustion indicators
    "misfire": [("combustion_impulse", 0.8)],
    "engine misfire": [("combustion_impulse", 0.9)],
    "detonation": [("combustion_impulse", 0.7)],
    "pre ignition": [("combustion_impulse", 0.7)],
    "exhaust leak": [("combustion_impulse", 0.4)],
    "catalytic converter": [("structural_resonance", 0.4), ("combustion_impulse", 0.3)],
    "exhaust manifold": [("combustion_impulse", 0.5)],
    "vacuum leak": [("combustion_impulse", 0.4)],
    "rough idle": [("combustion_impulse", 0.5)],
    # structural indicators
    "heat shield": [("structural_resonance", 0.7)],
    "exhaust pipe": [("structural_resonance", 0.4)],
    "body panel": [("structural_resonance", 0.5)],
    "suspension": [("structural_resonance", 0.4)],
    "strut": [("structural_resonance", 0.4)],
    "shock": [("structural_resonance", 0.3)],
    "sway bar": [("structural_resonance", 0.4)],
    "mount": [("structural_resonance", 0.5)],
    "engine mount": [("structural_resonance", 0.6)],
    "subframe": [("structural_resonance", 0.5)],
}

# Suggested trouble codes based on symptom keyword combinations
_SYMPTOM_CODE_MAP: dict[str, list[str]] = {
    "misfire": ["P0300"],
    "engine misfire": ["P0300"],
    "rough idle": ["P0300", "P0505"],
    "vacuum leak": ["P0171", "P0174"],
    "hissing under hood": ["P0171", "P0174"],
    "engine knock": ["P0325", "P0332"],
    "pinging": ["P0325"],
    "detonation": ["P0325"],
    "catalytic converter": ["P0420", "P0430"],
    "exhaust rattle": ["P0420"],
    "alternator": ["P0562", "P0622"],
    "charging": ["P0562"],
    "overheating": ["P0217"],
    "coolant": ["P0115", "P0128"],
    "thermostat": ["P0128"],
    "fuel pump": ["P0230", "P0231"],
    "transmission slipping": ["P0730", "P0894"],
    "harsh shift": ["P0780", "P0750"],
    "torque converter shudder": ["P0741"],
    "stalling": ["P0505", "P0300"],
    "poor fuel economy": ["P0171", "P0172"],
    "black smoke": ["P0172", "P0175"],
    "check engine light": ["P0300"],
    "abs light": ["C0035"],
    "wheel speed sensor": ["C0035", "C0040"],
    "oil pressure": ["P0520", "P0522"],
    "timing chain": ["P0016", "P0017"],
}


# ---------------------------------------------------------------------------
# Parser Core
# ---------------------------------------------------------------------------

def parse_symptoms(text: str) -> ParsedSymptoms:
    """
    Parse a free-text symptom description into structured diagnostic data.

    Args:
        text: User's description of the problem (e.g. "whining noise at
              highway speed that gets louder when turning").

    Returns:
        ParsedSymptoms with auto-filled BehavioralContext, matched keywords,
        confidence score, suggested codes, and location hints.
    """
    if not text or not text.strip():
        return ParsedSymptoms(original_text=text or "")

    # Normalize text
    normalized = _normalize_text(text)
    result = ParsedSymptoms(original_text=text)

    # --- Match noise character ---
    char_match = _match_longest_phrases(normalized, _NOISE_CHARACTER_KEYWORDS)
    if char_match:
        # Take the first (longest) match
        phrase, value = char_match[0]
        result.context.noise_character = value
        result.matched_keywords.append(phrase)

    # --- Match RPM dependency ---
    rpm_matches = _match_keyword_list(normalized, _RPM_KEYWORDS)
    if rpm_matches:
        result.context.rpm_dependency = True
        result.matched_keywords.extend(rpm_matches)

    # --- Match speed dependency ---
    speed_matches = _match_keyword_list(normalized, _SPEED_KEYWORDS)
    if speed_matches:
        result.context.speed_dependency = True
        result.matched_keywords.extend(speed_matches)

    # --- Match load dependency ---
    load_matches = _match_keyword_list(normalized, _LOAD_KEYWORDS)
    if load_matches:
        result.context.load_dependency = True
        result.matched_keywords.extend(load_matches)

    # --- Match cold dependency ---
    cold_matches = _match_keyword_list(normalized, _COLD_KEYWORDS)
    if cold_matches:
        result.context.cold_only = True
        result.matched_keywords.extend(cold_matches)

    # --- Match idle ---
    idle_matches = _match_keyword_list(normalized, _IDLE_KEYWORDS)
    if idle_matches:
        result.context.occurs_at_idle = True
        result.matched_keywords.extend(idle_matches)

    # --- Match perceived frequency ---
    if _match_keyword_list(normalized, _FREQ_HIGH_KEYWORDS):
        result.context.perceived_frequency = "high"
        result.matched_keywords.append("high frequency")
    elif _match_keyword_list(normalized, _FREQ_LOW_KEYWORDS):
        result.context.perceived_frequency = "low"
        result.matched_keywords.append("low frequency")
    elif _match_keyword_list(normalized, _FREQ_MID_KEYWORDS):
        result.context.perceived_frequency = "mid"
        result.matched_keywords.append("mid frequency")

    # --- Match intermittent ---
    intermittent_matches = _match_keyword_list(normalized, _INTERMITTENT_KEYWORDS)
    if intermittent_matches:
        result.context.intermittent = True
        result.matched_keywords.extend(intermittent_matches)

    # --- Match issue duration ---
    duration_match = _match_longest_phrases(normalized, _DURATION_MAP)
    if duration_match:
        phrase, value = duration_match[0]
        result.context.issue_duration = value
        result.matched_keywords.append(phrase)

    # --- Match vehicle type ---
    vtype_match = _match_longest_phrases(normalized, _VEHICLE_TYPE_MAP)
    if vtype_match:
        phrase, value = vtype_match[0]
        result.context.vehicle_type = value
        result.matched_keywords.append(phrase)

    # --- Match location hints ---
    loc_matches = _match_longest_phrases(normalized, _LOCATION_KEYWORDS)
    for phrase, value in loc_matches:
        result.location_hints.append(value)
        result.matched_keywords.append(phrase)

    # --- Match mechanical class hints ---
    class_matches = _match_class_hints(normalized)
    for phrase, hints in class_matches:
        result.matched_keywords.append(phrase)
        for cls, weight in hints:
            current = result.class_hints.get(cls, 0.0)
            result.class_hints[cls] = min(1.0, current + weight)

    # --- Suggest trouble codes ---
    suggested = set()
    code_matches = _match_longest_phrases(normalized, _SYMPTOM_CODE_MAP)
    for phrase, codes in code_matches:
        if isinstance(codes, list):
            suggested.update(codes)
    result.suggested_codes = sorted(suggested)

    # --- Infer class hints from symptom patterns ---
    # When the user doesn't name a specific component, we can still infer
    # the most likely mechanical class from the combination of behavioral
    # signals.  These are the "dang near close to certain" patterns.
    result.class_hints = _infer_class_hints_from_patterns(result)

    # --- Compute confidence ---
    # Based on: how many keywords matched vs text length
    word_count = len(normalized.split())
    keyword_count = len(result.matched_keywords)
    if word_count > 0:
        # Density of matched keywords relative to total words
        density = keyword_count / max(word_count, 1)
        # Also factor in whether we got the key fields
        has_character = result.context.noise_character != "unknown"
        has_dependency = any([
            result.context.rpm_dependency,
            result.context.speed_dependency,
            result.context.load_dependency,
            result.context.occurs_at_idle,
        ])
        has_location = len(result.location_hints) > 0

        # Base confidence from density (capped at 0.6)
        conf = min(0.6, density * 2.0)
        # Bonus for key fields
        if has_character:
            conf += 0.15
        if has_dependency:
            conf += 0.15
        if has_location:
            conf += 0.10

        result.confidence = min(1.0, conf)

    # Deduplicate matched keywords while preserving order
    seen = set()
    unique = []
    for kw in result.matched_keywords:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)
    result.matched_keywords = unique

    return result


# ---------------------------------------------------------------------------
# Symptom Pattern Inference
# ---------------------------------------------------------------------------
# When users describe symptoms without naming the specific component,
# combinations of behavioral signals strongly imply certain mechanical classes.
# These rules encode decades of diagnostic experience.

_PATTERN_RULES: list[dict] = [
    # --- Wheel / axle bearing ---
    # Hum/drone + speed-dependent is the #1 bearing indicator
    {
        "conditions": {"noise_character": ["hum_drone", "grind_scrape"],
                       "speed_dependency": True},
        "hints": [("rolling_element_bearing", 0.6)],
    },
    # Hum/drone + high mileage
    {
        "conditions": {"noise_character": ["hum_drone"],
                       "mileage_range": ["over_150k", "100k_150k"]},
        "hints": [("rolling_element_bearing", 0.4)],
    },
    # Grinding from wheel area at speed
    {
        "conditions": {"noise_character": ["grind_scrape"],
                       "speed_dependency": True},
        "hints": [("rolling_element_bearing", 0.5)],
    },

    # --- Belt / friction ---
    # Squeal + cold = classic belt
    {
        "conditions": {"noise_character": ["squeal"],
                       "cold_only": True},
        "hints": [("belt_drive_friction", 0.7)],
    },
    # Squeal + RPM dependent
    {
        "conditions": {"noise_character": ["squeal"],
                       "rpm_dependency": True},
        "hints": [("belt_drive_friction", 0.5)],
    },
    # Squeal + high frequency
    {
        "conditions": {"noise_character": ["squeal"],
                       "perceived_frequency": ["high"]},
        "hints": [("belt_drive_friction", 0.4)],
    },

    # --- Combustion / misfire ---
    # Knock/tap + idle = engine knock or misfire
    {
        "conditions": {"noise_character": ["knock_tap"],
                       "occurs_at_idle": True},
        "hints": [("combustion_impulse", 0.6)],
    },
    # Knock/tap + RPM dependent
    {
        "conditions": {"noise_character": ["knock_tap"],
                       "rpm_dependency": True},
        "hints": [("combustion_impulse", 0.5)],
    },
    # Click/tick + RPM + idle
    {
        "conditions": {"noise_character": ["click_tick"],
                       "rpm_dependency": True},
        "hints": [("combustion_impulse", 0.4)],
    },

    # --- Gear mesh / drivetrain ---
    # Whine + speed dependent + load
    {
        "conditions": {"noise_character": ["whine"],
                       "speed_dependency": True,
                       "load_dependency": True},
        "hints": [("gear_mesh_drivetrain", 0.5)],
    },
    # Whine + speed dependent (without load -> could be bearing too)
    {
        "conditions": {"noise_character": ["whine"],
                       "speed_dependency": True},
        "hints": [("gear_mesh_drivetrain", 0.3), ("rolling_element_bearing", 0.2)],
    },

    # --- Hydraulic ---
    # Whine + load dependent (no speed)
    {
        "conditions": {"noise_character": ["whine"],
                       "load_dependency": True},
        "hints": [("hydraulic_flow_cavitation", 0.4)],
    },
    # Hiss from engine bay
    {
        "conditions": {"noise_character": ["hiss"]},
        "hints": [("combustion_impulse", 0.3)],  # vacuum leak
    },

    # --- Structural ---
    # Rattle + intermittent
    {
        "conditions": {"noise_character": ["rattle_buzz"],
                       "intermittent": True},
        "hints": [("structural_resonance", 0.5)],
    },
    # Rattle + speed dependent
    {
        "conditions": {"noise_character": ["rattle_buzz"],
                       "speed_dependency": True},
        "hints": [("structural_resonance", 0.4)],
    },

    # --- Electrical ---
    # Whine + RPM but NOT speed or load
    {
        "conditions": {"noise_character": ["whine"],
                       "rpm_dependency": True},
        "hints": [("electrical_interference", 0.3)],
    },
]


def _infer_class_hints_from_patterns(result: ParsedSymptoms) -> dict[str, float]:
    """
    Infer mechanical class hints from combinations of parsed behavioral
    signals.  Merges with any existing class_hints from direct keyword
    matching (e.g. user said "wheel bearing").
    """
    hints = dict(result.class_hints)  # Start with existing direct hints
    ctx = result.context

    for rule in _PATTERN_RULES:
        conditions = rule["conditions"]
        match = True

        for field, expected in conditions.items():
            actual = getattr(ctx, field, None)

            if isinstance(expected, bool):
                if actual != expected:
                    match = False
                    break
            elif isinstance(expected, list):
                if actual not in expected:
                    match = False
                    break
            else:
                if actual != expected:
                    match = False
                    break

        if match:
            for cls, weight in rule["hints"]:
                current = hints.get(cls, 0.0)
                hints[cls] = min(1.0, current + weight)

    return hints


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalize_text(text: str) -> str:
    """Lowercase, strip punctuation (keep spaces), collapse whitespace."""
    text = text.lower().strip()
    # Replace common punctuation with spaces
    text = re.sub(r"[.,;:!?\"'()\[\]{}/\\]", " ", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text


def _match_longest_phrases(text: str, phrase_map: dict) -> list[tuple[str, any]]:
    """
    Match phrases from a dict against text, longest first.
    Returns list of (matched_phrase, value) pairs.
    """
    # Sort phrases by length (longest first) for greedy matching
    sorted_phrases = sorted(phrase_map.keys(), key=len, reverse=True)
    matches = []
    matched_spans = set()

    for phrase in sorted_phrases:
        # Check if phrase appears in text
        idx = text.find(phrase.lower())
        if idx >= 0:
            # Check for overlap with already-matched spans
            span = range(idx, idx + len(phrase))
            if not any(i in matched_spans for i in span):
                matches.append((phrase, phrase_map[phrase]))
                matched_spans.update(span)

    return matches


def _match_keyword_list(text: str, keywords: list[str]) -> list[str]:
    """Match keywords from a list against text. Returns matched keywords."""
    matches = []
    for kw in sorted(keywords, key=len, reverse=True):
        if kw.lower() in text:
            matches.append(kw)
    return matches


def _match_class_hints(text: str) -> list[tuple[str, list[tuple[str, float]]]]:
    """
    Match mechanical class hint keywords against text.
    Returns list of (phrase, [(class, weight), ...]) tuples.
    """
    sorted_phrases = sorted(_CLASS_HINT_KEYWORDS.keys(), key=len, reverse=True)
    matches = []
    matched_spans = set()

    for phrase in sorted_phrases:
        idx = text.find(phrase.lower())
        if idx >= 0:
            span = range(idx, idx + len(phrase))
            if not any(i in matched_spans for i in span):
                matches.append((phrase, _CLASS_HINT_KEYWORDS[phrase]))
                matched_spans.update(span)

    return matches
