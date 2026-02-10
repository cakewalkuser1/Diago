"""
Matching Engine
Compares audio fingerprints against the database of known fault signatures
and returns ranked match results with confidence scores.

The matching algorithm:
1. Extract all hash values from the input fingerprints
2. Query the database for matching hashes across all stored signatures
3. Group matches by signature and count hash hits
4. Score each signature based on the ratio of matching hashes
5. Apply time-coherence analysis to validate matches
6. Return ranked results above the confidence threshold
"""

from collections import defaultdict
from dataclasses import dataclass

from core.fingerprint import Fingerprint
from database.db_manager import DatabaseManager, MatchResult


# Minimum confidence threshold (percentage) to report a match
DEFAULT_CONFIDENCE_THRESHOLD = 15.0

# Minimum number of hash matches required to consider a signature
MIN_HASH_MATCHES = 3


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


def match_fingerprint(
    fingerprints: list[Fingerprint],
    db_manager: DatabaseManager,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> list[MatchResult]:
    """
    Match input fingerprints against all known fault signatures in the database.

    Args:
        fingerprints: List of Fingerprint objects from the input audio.
        db_manager: Database manager instance.
        confidence_threshold: Minimum confidence percentage to include in results.

    Returns:
        List of MatchResult objects, sorted by confidence (highest first).
    """
    if not fingerprints:
        return []

    # Step 1: Extract hash values from input fingerprints
    input_hashes = [fp.hash_value for fp in fingerprints]
    input_hash_set = set(input_hashes)

    # Build a lookup from hash -> list of time offsets in input
    input_hash_times: dict[int, list[float]] = defaultdict(list)
    for fp in fingerprints:
        input_hash_times[fp.hash_value].append(fp.time_offset)

    # Step 2: Query database for matching hashes
    db_matches = db_manager.find_matching_hashes(list(input_hash_set))

    if not db_matches:
        return []

    # Step 3: Group matches by signature
    sig_matches: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for sig_id, hash_val, time_offset in db_matches:
        sig_matches[sig_id].append((hash_val, time_offset))

    # Step 4: Score each signature
    results = []

    for sig_id, matches in sig_matches.items():
        # Count unique hash matches
        unique_matching_hashes = len(set(h for h, _ in matches))

        if unique_matching_hashes < MIN_HASH_MATCHES:
            continue

        # Get total hashes for this signature
        total_sig_hashes = db_manager.get_hash_count_by_signature(sig_id)

        if total_sig_hashes == 0:
            continue

        # Base confidence: ratio of matching hashes
        hash_ratio = unique_matching_hashes / total_sig_hashes

        # Time coherence: check if matching hashes have consistent time offsets
        time_coherence = _compute_time_coherence(
            matches, input_hash_times
        )

        # Combined confidence score
        # Weight: 60% hash ratio, 40% time coherence
        raw_confidence = (0.6 * hash_ratio + 0.4 * time_coherence) * 100

        # Cap at 99%
        confidence = min(raw_confidence, 99.0)

        if confidence >= confidence_threshold:
            # Retrieve signature details
            sig = db_manager.get_signature_by_id(sig_id)
            if sig is not None:
                results.append(MatchResult(
                    fault_name=sig.name,
                    confidence_pct=round(confidence, 1),
                    trouble_codes=sig.associated_codes or "",
                    description=sig.description or "",
                    category=sig.category,
                    signature_id=sig.id,
                ))

    # Sort by confidence descending
    results.sort(key=lambda r: r.confidence_pct, reverse=True)

    return results


def match_fingerprint_detailed(
    fingerprints: list[Fingerprint],
    db_manager: DatabaseManager,
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> list[DetailedMatch]:
    """
    Like match_fingerprint but returns extended analysis data.
    Useful for debugging and detailed diagnostics display.
    """
    if not fingerprints:
        return []

    input_hashes = [fp.hash_value for fp in fingerprints]
    input_hash_set = set(input_hashes)

    input_hash_times: dict[int, list[float]] = defaultdict(list)
    for fp in fingerprints:
        input_hash_times[fp.hash_value].append(fp.time_offset)

    db_matches = db_manager.find_matching_hashes(list(input_hash_set))

    if not db_matches:
        return []

    sig_matches: dict[int, list[tuple[int, float]]] = defaultdict(list)
    for sig_id, hash_val, time_offset in db_matches:
        sig_matches[sig_id].append((hash_val, time_offset))

    results = []

    for sig_id, matches in sig_matches.items():
        unique_matching_hashes = len(set(h for h, _ in matches))

        if unique_matching_hashes < MIN_HASH_MATCHES:
            continue

        total_sig_hashes = db_manager.get_hash_count_by_signature(sig_id)
        if total_sig_hashes == 0:
            continue

        hash_ratio = unique_matching_hashes / total_sig_hashes
        time_coherence = _compute_time_coherence(matches, input_hash_times)
        raw_confidence = (0.6 * hash_ratio + 0.4 * time_coherence) * 100
        confidence = min(raw_confidence, 99.0)

        if confidence >= confidence_threshold:
            sig = db_manager.get_signature_by_id(sig_id)
            if sig is not None:
                results.append(DetailedMatch(
                    fault_name=sig.name,
                    confidence_pct=round(confidence, 1),
                    trouble_codes=sig.associated_codes or "",
                    description=sig.description or "",
                    category=sig.category,
                    signature_id=sig.id,
                    matching_hashes=unique_matching_hashes,
                    total_signature_hashes=total_sig_hashes,
                    time_coherence_score=round(time_coherence, 3),
                ))

    results.sort(key=lambda r: r.confidence_pct, reverse=True)
    return results


def match_with_trouble_codes(
    fingerprints: list[Fingerprint],
    db_manager: DatabaseManager,
    user_codes: list[str],
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
) -> list[MatchResult]:
    """
    Match fingerprints and boost confidence for signatures whose
    associated trouble codes match the user-entered codes.

    This gives priority to faults that align with the OBD-II data.

    Args:
        fingerprints: Input audio fingerprints.
        db_manager: Database manager.
        user_codes: List of user-entered trouble codes (e.g., ["P0301", "P0420"]).
        confidence_threshold: Minimum confidence to include.

    Returns:
        List of MatchResult objects with code-boosted confidence.
    """
    # Get base matches
    results = match_fingerprint(fingerprints, db_manager, confidence_threshold=0)

    if not user_codes or not results:
        # No codes to boost, just filter by threshold
        return [r for r in results if r.confidence_pct >= confidence_threshold]

    # Normalize user codes
    user_code_set = set(code.strip().upper() for code in user_codes)

    # Boost confidence for matching codes
    boosted_results = []
    for result in results:
        sig_codes = set(
            c.strip().upper()
            for c in result.trouble_codes.split(",")
            if c.strip()
        )

        # If any user code matches a signature code, boost confidence
        code_overlap = user_code_set & sig_codes
        if code_overlap:
            # Boost by up to 20% based on code match
            boost = min(20.0, len(code_overlap) * 10.0)
            boosted_confidence = min(result.confidence_pct + boost, 99.0)
            result = MatchResult(
                fault_name=result.fault_name,
                confidence_pct=round(boosted_confidence, 1),
                trouble_codes=result.trouble_codes,
                description=result.description,
                category=result.category,
                signature_id=result.signature_id,
            )

        if result.confidence_pct >= confidence_threshold:
            boosted_results.append(result)

    boosted_results.sort(key=lambda r: r.confidence_pct, reverse=True)
    return boosted_results


def _compute_time_coherence(
    db_matches: list[tuple[int, float]],
    input_hash_times: dict[int, list[float]],
) -> float:
    """
    Compute time coherence between database matches and input fingerprints.

    Time coherence measures whether matching hashes occur at consistent
    time offsets relative to each other. High coherence means the pattern
    appears at a consistent position, not just random hash collisions.

    Returns:
        Score between 0.0 (no coherence) and 1.0 (perfect coherence).
    """
    if len(db_matches) < 2:
        return 0.0

    # Compute time deltas between each DB match and its input occurrence
    deltas = []
    for hash_val, db_time in db_matches:
        if hash_val in input_hash_times:
            for input_time in input_hash_times[hash_val]:
                deltas.append(input_time - db_time)

    if len(deltas) < 2:
        return 0.0

    # Find the most common time delta (modal offset)
    # Using histogram-based approach
    import numpy as np

    deltas_array = np.array(deltas)

    # If all deltas are the same, perfect coherence
    delta_range = deltas_array.max() - deltas_array.min()
    if delta_range < 0.01:
        return 1.0

    # Bin the deltas and find the peak
    n_bins = min(50, len(deltas))
    hist, bin_edges = np.histogram(deltas_array, bins=n_bins)

    # The coherence score is the fraction of deltas in the modal bin
    # (plus neighboring bins for tolerance)
    peak_bin = np.argmax(hist)
    start = max(0, peak_bin - 1)
    end = min(len(hist), peak_bin + 2)
    peak_count = hist[start:end].sum()

    coherence = peak_count / len(deltas)

    return min(coherence, 1.0)
