"""
LLM Reasoning Module (Optional, Bypassable)
Provides constrained natural-language reasoning over the diagnostic
engine's scored output.

DISABLED BY DEFAULT. The diagnostic pipeline works fully without this.
When enabled, it sends the top-scored mechanical classes and extracted
features to an LLM for a human-readable explanation.

Guardrails:
- The LLM cannot introduce new classes
- The LLM cannot override penalty decisions
- The LLM must output structured JSON
- The LLM only explains what the math already decided

Supported backends (pluggable):
- OpenAI (GPT-4o, GPT-4o-mini)
- Anthropic (Claude)
- Ollama (local LLM)
- None (disabled, default)
"""

import json
from dataclasses import dataclass
from typing import Any

from core.feature_extraction import AudioFeatures
from core.diagnostic_engine import (
    MECHANICAL_CLASSES, CLASS_DISPLAY_NAMES, CLASS_DESCRIPTIONS,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LLM_ENABLED = False  # Set to True to enable LLM reasoning

# Provider: "openai", "anthropic", "ollama", or None
LLM_PROVIDER = None

# Provider-specific settings
LLM_CONFIG = {
    "openai": {
        "model": "gpt-4o-mini",
        "api_key": "",  # Set via environment variable OPENAI_API_KEY
    },
    "anthropic": {
        "model": "claude-sonnet-4-20250514",
        "api_key": "",  # Set via environment variable ANTHROPIC_API_KEY
    },
    "ollama": {
        "model": "llama3.1",
        "base_url": "http://localhost:11434",
    },
}


# ---------------------------------------------------------------------------
# Prompt Construction (with guardrails)
# ---------------------------------------------------------------------------

def build_structured_prompt(
    class_scores: dict[str, float],
    features: dict,
    penalties: dict[str, float],
    top_n: int = 3,
) -> dict:
    """
    Build a structured prompt for the LLM with guardrails.

    Args:
        class_scores: Normalized class probabilities.
        features: Extracted feature dict.
        penalties: Penalties applied per class.
        top_n: Number of top classes to include.

    Returns:
        Structured prompt dict for the LLM.
    """
    # Select top N classes
    sorted_classes = sorted(
        class_scores.items(), key=lambda x: x[1], reverse=True
    )
    top_classes = sorted_classes[:top_n]

    allowed_classes = []
    for cls, score in top_classes:
        allowed_classes.append({
            "class": cls,
            "display_name": CLASS_DISPLAY_NAMES.get(cls, cls),
            "probability": round(score, 4),
            "penalty_applied": round(penalties.get(cls, 0.0), 4),
            "description": CLASS_DESCRIPTIONS.get(cls, ""),
        })

    return {
        "system": (
            "You are an automotive diagnostic assistant. "
            "You analyze audio feature data and mechanical class scores "
            "to provide a clear, actionable diagnostic explanation. "
            "You MUST follow the constraints below."
        ),
        "allowed_classes": allowed_classes,
        "features": {
            k: round(v, 4) if isinstance(v, float) else v
            for k, v in features.items()
        },
        "constraints": [
            "Do NOT introduce any mechanical classes not listed in allowed_classes.",
            "Do NOT override or contradict the probability scores provided.",
            "Do NOT override any penalties that have been applied.",
            "Explain WHY the top class scored highest based on the features.",
            "If penalties were applied to a class, explain what physics rule was violated.",
            "Provide practical next-step recommendations for the vehicle owner.",
            "Output valid JSON with keys: explanation, top_diagnosis, recommendations, confidence_note.",
        ],
    }


def format_prompt_as_text(prompt: dict) -> str:
    """Convert the structured prompt into a text string for the LLM."""
    lines = [
        prompt["system"],
        "",
        "=== SCORED MECHANICAL CLASSES ===",
    ]

    for cls_info in prompt["allowed_classes"]:
        lines.append(
            f"- {cls_info['display_name']}: {cls_info['probability']:.1%} "
            f"(penalty: {cls_info['penalty_applied']:.2f})"
        )
        lines.append(f"  Description: {cls_info['description']}")

    lines.extend([
        "",
        "=== EXTRACTED FEATURES ===",
    ])
    for key, val in prompt["features"].items():
        lines.append(f"- {key}: {val}")

    lines.extend([
        "",
        "=== CONSTRAINTS ===",
    ])
    for c in prompt["constraints"]:
        lines.append(f"- {c}")

    lines.extend([
        "",
        "Based on the above data and constraints, provide your analysis as JSON.",
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# LLM Invocation
# ---------------------------------------------------------------------------

def run_llm_reasoning(
    class_scores: dict[str, float],
    features: AudioFeatures,
    penalties: dict[str, float],
) -> str | None:
    """
    Run LLM reasoning if enabled.

    Args:
        class_scores: Normalized class probabilities.
        features: AudioFeatures instance.
        penalties: Penalty dict.

    Returns:
        LLM narrative string, or None if disabled/failed.
    """
    if not LLM_ENABLED or LLM_PROVIDER is None:
        return None

    prompt_data = build_structured_prompt(
        class_scores,
        features.to_dict() if hasattr(features, "to_dict") else features,
        penalties,
    )
    prompt_text = format_prompt_as_text(prompt_data)

    try:
        if LLM_PROVIDER == "openai":
            return _call_openai(prompt_text)
        elif LLM_PROVIDER == "anthropic":
            return _call_anthropic(prompt_text)
        elif LLM_PROVIDER == "ollama":
            return _call_ollama(prompt_text)
        else:
            return None
    except Exception as e:
        return f"[LLM error: {e}]"


def _call_openai(prompt: str) -> str | None:
    """Call OpenAI API."""
    import os
    try:
        import openai
    except ImportError:
        return "[OpenAI package not installed. Run: pip install openai]"

    config = LLM_CONFIG["openai"]
    api_key = config["api_key"] or os.environ.get("OPENAI_API_KEY", "")

    if not api_key:
        return "[OpenAI API key not set. Set OPENAI_API_KEY environment variable.]"

    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=config["model"],
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=1000,
    )

    return response.choices[0].message.content


def _call_anthropic(prompt: str) -> str | None:
    """Call Anthropic API."""
    import os
    try:
        import anthropic
    except ImportError:
        return "[Anthropic package not installed. Run: pip install anthropic]"

    config = LLM_CONFIG["anthropic"]
    api_key = config["api_key"] or os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        return "[Anthropic API key not set. Set ANTHROPIC_API_KEY environment variable.]"

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=config["model"],
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text


def _call_ollama(prompt: str) -> str | None:
    """Call local Ollama instance."""
    import urllib.request
    import urllib.error

    config = LLM_CONFIG["ollama"]
    url = f"{config['base_url']}/api/generate"

    payload = json.dumps({
        "model": config["model"],
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3},
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", None)
    except urllib.error.URLError:
        return "[Ollama not reachable. Is it running on localhost:11434?]"


# ---------------------------------------------------------------------------
# Narrative generation (no-LLM fallback)
# ---------------------------------------------------------------------------

def generate_fallback_narrative(
    class_scores: dict[str, float],
    features: dict,
    penalties: dict[str, float],
    is_ambiguous: bool,
) -> str:
    """
    Generate a human-readable narrative without an LLM.
    Used when LLM is disabled or fails.

    Args:
        class_scores: Normalized class probabilities.
        features: Feature dict.
        penalties: Penalty dict.
        is_ambiguous: Whether the result is ambiguous.

    Returns:
        Plain-text diagnostic narrative.
    """
    if is_ambiguous:
        return (
            "The analysis could not determine a clear mechanical class. "
            "The audio features do not strongly match any single fault category. "
            "Recommendation: record additional audio under different conditions "
            "(e.g., varying RPM, with/without load) for a more definitive diagnosis."
        )

    sorted_classes = sorted(
        class_scores.items(), key=lambda x: x[1], reverse=True
    )

    lines = []

    # Top class explanation
    top_cls, top_score = sorted_classes[0]
    display = CLASS_DISPLAY_NAMES.get(top_cls, top_cls)
    desc = CLASS_DESCRIPTIONS.get(top_cls, "")

    lines.append(
        f"Primary diagnosis: {display} ({top_score:.0%} probability)."
    )
    lines.append(desc)

    # Explain key features that contributed
    weights_for_top = {
        name: val for name, val in
        (features.items() if isinstance(features, dict) else [])
    }

    # Note any penalties
    penalty = penalties.get(top_cls, 0.0)
    if penalty > 0:
        lines.append(
            f"\nNote: A penalty of {penalty:.2f} was applied due to "
            "feature-constraint conflicts, but this class still scored highest."
        )

    # Secondary classes
    if len(sorted_classes) > 1:
        second_cls, second_score = sorted_classes[1]
        if second_score > 0.15:
            second_display = CLASS_DISPLAY_NAMES.get(second_cls, second_cls)
            lines.append(
                f"\nSecondary consideration: {second_display} "
                f"({second_score:.0%}). "
                "Further testing may help differentiate."
            )

    return "\n".join(lines)
