"""
Diago Shared Data Models
Canonical dataclass definitions used across core, database, and API layers.
Consolidates models that were previously scattered across modules.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Database models (originally in database/db_manager.py)
# ---------------------------------------------------------------------------

@dataclass
class FaultSignature:
    """Represents a known fault audio signature."""
    id: int
    name: str
    description: str
    category: str
    associated_codes: str
    created_at: str = ""


@dataclass
class AnalysisSession:
    """Represents a user analysis session."""
    id: int
    timestamp: str
    audio_path: str
    user_codes: str
    notes: str
    duration_seconds: float = 0.0


@dataclass
class MatchResult:
    """Represents a match result for a session."""
    fault_name: str
    confidence_pct: float
    trouble_codes: str
    description: str
    category: str
    signature_id: int = 0


# ---------------------------------------------------------------------------
# Trouble code models (originally in database/trouble_code_lookup.py)
# ---------------------------------------------------------------------------

@dataclass
class CodeDefinition:
    """Represents a single OBD-II trouble code definition."""
    code: str
    description: str
    system: str
    subsystem: str
    mechanical_classes: list[str] = field(default_factory=list)
    symptoms: list[str] = field(default_factory=list)
    severity: str = "medium"


# ---------------------------------------------------------------------------
# Diagnostic intake (structured input for pattern matching)
# ---------------------------------------------------------------------------

@dataclass
class VehicleIntake:
    """Vehicle identification for diagnostic intake."""
    year: int | None = None
    make: str = ""
    model: str = ""
    engine: str = ""  # e.g. "2.5L 2AR-FE"


@dataclass
class FuelTrimIntake:
    """Fuel trim data (STFT/LTFT); per-bank later if needed."""
    stft: float | None = None  # short-term fuel trim %
    ltft: float | None = None  # long-term fuel trim %


@dataclass
class EnvironmentIntake:
    """Environment/operating conditions derived from BehavioralContext."""
    cold_start: bool = False
    at_idle: bool = False
    under_load: bool = False


@dataclass
class DiagnosticIntake:
    """Canonical structured input for the diagnostic pattern layer."""
    vehicle: VehicleIntake = field(default_factory=VehicleIntake)
    symptoms: list[str] = field(default_factory=list)  # normalized symptom keys/phrases
    dtcs: list[str] = field(default_factory=list)
    fuel_trims: FuelTrimIntake = field(default_factory=FuelTrimIntake)
    environment: EnvironmentIntake = field(default_factory=EnvironmentIntake)


# ---------------------------------------------------------------------------
# Diagnostic models (originally in core/diagnostic_engine.py)
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
    diagnostic_intake: Optional["DiagnosticIntake"] = None  # Structured intake for pattern layer
    ranked_failure_modes: list[Any] = field(default_factory=list)  # list[FailureModeMatch] from pattern engine


# ---------------------------------------------------------------------------
# Fingerprint models (originally in core/fingerprint.py)
# ---------------------------------------------------------------------------

@dataclass
class Fingerprint:
    """A single fingerprint hash with its time offset."""
    hash_value: int
    time_offset: float  # seconds


@dataclass
class PeakPoint:
    """A detected spectral peak."""
    freq_bin: int
    time_bin: int
    frequency: float   # Hz
    time: float         # seconds
    amplitude: float    # dB


# ---------------------------------------------------------------------------
# Matcher models (originally in core/matcher.py)
# ---------------------------------------------------------------------------

@dataclass
class DetailedMatch:
    """Extended match result with additional analysis data."""
    fault_name: str
    confidence_pct: float
    trouble_codes: str
    description: str
    category: str
    signature_id: int
    matching_hashes: int
    total_signature_hashes: int
    time_coherence_score: float


# ---------------------------------------------------------------------------
# Search models (originally in core/tavily_search.py)
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    """A single web search result."""
    title: str
    url: str
    snippet: str
    score: float = 0.0


# ---------------------------------------------------------------------------
# Knowledge base models (originally in core/knowledge_base.py)
# ---------------------------------------------------------------------------

@dataclass
class KnowledgeChunk:
    """A single retrievable knowledge chunk."""
    id: str
    title: str
    content: str
    category: str  # common_failures, diagnostic_trees, etc.
    keywords: list[str] = field(default_factory=list)
    vehicle_types: list[str] = field(default_factory=list)
    mileage_range: str = ""
    relevance: float = 0.0  # Set during retrieval


# ---------------------------------------------------------------------------
# Agent models (originally in core/mechanic_agent.py)
# ---------------------------------------------------------------------------

@dataclass
class Message:
    """A single message in the conversation."""
    role: str  # "user", "assistant", "system", "tool"
    content: str
    tool_calls: list[dict] = field(default_factory=list)
    tool_call_id: str = ""
    name: str = ""  # tool name for tool responses


# ---------------------------------------------------------------------------
# Symptom parser models (originally in core/symptom_parser.py)
# ---------------------------------------------------------------------------

@dataclass
class ParsedSymptoms:
    """Result of parsing a user's symptom description."""
    context: Any = None  # BehavioralContext (imported at runtime to avoid circular)
    matched_keywords: list[str] = field(default_factory=list)
    confidence: float = 0.0
    suggested_codes: list[str] = field(default_factory=list)
    location_hints: list[str] = field(default_factory=list)
    class_hints: dict[str, float] = field(default_factory=dict)
    original_text: str = ""
