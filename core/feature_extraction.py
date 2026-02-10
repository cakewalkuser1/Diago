"""
Feature Extraction Module (v2 -- Accuracy Upgrade)
Computes spectral, temporal, sub-band, and behavioral features from
preprocessed automotive audio for the diagnostic scoring engine.

Spectral features (frequency domain):
- spectral_centroid: weighted mean frequency
- spectral_bandwidth: spread around centroid
- spectral_flatness: Wiener entropy (0=tonal, 1=noisy)
- harmonic_ratio: harmonic energy / total energy
- spectral_rolloff: frequency below which 85% of energy lies
- dominant_frequency: actual peak frequency bin
- spectral_centroid_std: variation of centroid across frames
- spectral_entropy: Shannon entropy of the power spectrum

Sub-band energy features (5 automotive-relevant bands):
- band_low (20-300 Hz): combustion rumble, structural
- band_low_mid (300-1000 Hz): gear mesh fundamental
- band_mid (1000-3000 Hz): bearing, belt, hydraulic
- band_high_mid (3000-6000 Hz): bearing harmonics, electrical
- band_high (6000-8000 Hz): friction, high-freq electrical

Temporal features (time domain):
- rms_energy: overall signal power
- amplitude_variance: envelope fluctuation
- periodicity_score: autocorrelation peak strength
- transient_density: impulse onsets per second
- crest_factor: peak/RMS ratio (impulsiveness)
- zero_crossing_rate: sign-change rate (frequency proxy)

Behavioral context (user-provided via GUI):
- Original 6 booleans + noise character, perceived frequency,
  intermittent, issue duration, vehicle type, mileage, maintenance
"""

from dataclasses import dataclass, field, asdict

import numpy as np
from scipy import signal as sig


# ---------------------------------------------------------------------------
# Enum-like string constants for behavioral context
# ---------------------------------------------------------------------------

NOISE_CHARACTERS = [
    "unknown", "whine", "squeal", "knock_tap", "rattle_buzz",
    "hum_drone", "click_tick", "grind_scrape", "hiss",
]

PERCEIVED_FREQUENCIES = ["unknown", "low", "mid", "high"]

ISSUE_DURATIONS = ["unknown", "just_started", "days", "weeks", "months"]

VEHICLE_TYPES = [
    "unknown", "sedan", "suv_truck", "sports", "diesel", "hybrid_ev",
]

MILEAGE_RANGES = [
    "unknown", "under_50k", "50k_100k", "100k_150k", "over_150k",
]

RECENT_MAINTENANCE = [
    "unknown", "none", "oil_change", "belt_replacement",
    "brake_work", "suspension_work",
]


# ---------------------------------------------------------------------------
# Behavioral context (user-provided via GUI)
# ---------------------------------------------------------------------------

@dataclass
class BehavioralContext:
    """
    User-observed behavioral characteristics of the noise.
    Boolean flags + categorical dropdowns from the GUI.
    """
    # Original boolean flags
    rpm_dependency: bool = False
    speed_dependency: bool = False
    load_dependency: bool = False
    cold_only: bool = False
    occurs_at_idle: bool = False
    mechanical_localization: bool = False

    # New categorical context
    noise_character: str = "unknown"
    perceived_frequency: str = "unknown"
    intermittent: bool = False
    issue_duration: str = "unknown"
    vehicle_type: str = "unknown"
    mileage_range: str = "unknown"
    recent_maintenance: str = "unknown"

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Combined feature set (v2)
# ---------------------------------------------------------------------------

@dataclass
class AudioFeatures:
    """Complete feature set for the diagnostic engine."""
    # Spectral (original 4 + 4 new)
    spectral_centroid: float = 0.0
    spectral_bandwidth: float = 0.0
    spectral_flatness: float = 0.0
    harmonic_ratio: float = 0.0
    spectral_rolloff: float = 0.0
    dominant_frequency: float = 0.0
    spectral_centroid_std: float = 0.0
    spectral_entropy: float = 0.0

    # Sub-band energies (5 bands)
    band_low: float = 0.0          # 20-300 Hz
    band_low_mid: float = 0.0      # 300-1000 Hz
    band_mid: float = 0.0          # 1000-3000 Hz
    band_high_mid: float = 0.0     # 3000-6000 Hz
    band_high: float = 0.0         # 6000-8000 Hz

    # Temporal (original 4 + 2 new)
    rms_energy: float = 0.0
    amplitude_variance: float = 0.0
    periodicity_score: float = 0.0
    transient_density: float = 0.0
    crest_factor: float = 0.0
    zero_crossing_rate: float = 0.0

    # Behavioral booleans (from user context)
    rpm_dependency: float = 0.0
    speed_dependency: float = 0.0
    load_dependency: float = 0.0
    cold_only: float = 0.0
    occurs_at_idle: float = 0.0
    mechanical_localization: float = 0.0
    intermittent: float = 0.0

    # Behavioral categorical (one-hot encoded)
    char_whine: float = 0.0
    char_squeal: float = 0.0
    char_knock_tap: float = 0.0
    char_rattle_buzz: float = 0.0
    char_hum_drone: float = 0.0
    char_click_tick: float = 0.0
    char_grind_scrape: float = 0.0
    char_hiss: float = 0.0

    freq_low: float = 0.0
    freq_mid: float = 0.0
    freq_high: float = 0.0

    dur_just_started: float = 0.0
    dur_days: float = 0.0
    dur_weeks: float = 0.0
    dur_months: float = 0.0

    veh_sedan: float = 0.0
    veh_suv_truck: float = 0.0
    veh_sports: float = 0.0
    veh_diesel: float = 0.0
    veh_hybrid_ev: float = 0.0

    mileage_under_50k: float = 0.0
    mileage_50k_100k: float = 0.0
    mileage_100k_150k: float = 0.0
    mileage_over_150k: float = 0.0

    maint_none: float = 0.0
    maint_oil_change: float = 0.0
    maint_belt_replacement: float = 0.0
    maint_brake_work: float = 0.0
    maint_suspension_work: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_features(
    audio: np.ndarray,
    sr: int = 44100,
    context: BehavioralContext | None = None,
) -> AudioFeatures:
    """
    Extract all features from preprocessed audio and user context.

    Args:
        audio: Preprocessed mono float32 numpy array.
        sr: Sample rate.
        context: User-provided behavioral observations.

    Returns:
        AudioFeatures dataclass with all computed values.
    """
    if len(audio) == 0:
        return AudioFeatures()

    spectral = compute_spectral_features(audio, sr)
    temporal = compute_temporal_features(audio, sr)
    subbands = compute_subband_energies(audio, sr)

    ctx = context or BehavioralContext()
    behavioral = _encode_behavioral_context(ctx)

    return AudioFeatures(
        # Spectral
        spectral_centroid=spectral["spectral_centroid"],
        spectral_bandwidth=spectral["spectral_bandwidth"],
        spectral_flatness=spectral["spectral_flatness"],
        harmonic_ratio=spectral["harmonic_ratio"],
        spectral_rolloff=spectral["spectral_rolloff"],
        dominant_frequency=spectral["dominant_frequency"],
        spectral_centroid_std=spectral["spectral_centroid_std"],
        spectral_entropy=spectral["spectral_entropy"],
        # Sub-bands
        band_low=subbands["band_low"],
        band_low_mid=subbands["band_low_mid"],
        band_mid=subbands["band_mid"],
        band_high_mid=subbands["band_high_mid"],
        band_high=subbands["band_high"],
        # Temporal
        rms_energy=temporal["rms_energy"],
        amplitude_variance=temporal["amplitude_variance"],
        periodicity_score=temporal["periodicity_score"],
        transient_density=temporal["transient_density"],
        crest_factor=temporal["crest_factor"],
        zero_crossing_rate=temporal["zero_crossing_rate"],
        # Behavioral
        **behavioral,
    )


def extract_features_from_context(
    context: BehavioralContext,
) -> AudioFeatures:
    """
    Build an AudioFeatures object from BehavioralContext alone (no audio).

    All spectral/temporal features default to 0.0; only behavioral
    features are populated.  This allows the scoring engine to run
    in text-only mode.
    """
    behavioral = _encode_behavioral_context(context)
    return AudioFeatures(**behavioral)


# ---------------------------------------------------------------------------
# Behavioral context encoding
# ---------------------------------------------------------------------------

def _encode_behavioral_context(ctx: BehavioralContext) -> dict:
    """Convert BehavioralContext into float feature dict for AudioFeatures."""
    d: dict[str, float] = {}

    # Boolean flags
    d["rpm_dependency"] = float(ctx.rpm_dependency)
    d["speed_dependency"] = float(ctx.speed_dependency)
    d["load_dependency"] = float(ctx.load_dependency)
    d["cold_only"] = float(ctx.cold_only)
    d["occurs_at_idle"] = float(ctx.occurs_at_idle)
    d["mechanical_localization"] = float(ctx.mechanical_localization)
    d["intermittent"] = float(ctx.intermittent)

    # Noise character (one-hot)
    for char in NOISE_CHARACTERS:
        if char == "unknown":
            continue
        d[f"char_{char}"] = 1.0 if ctx.noise_character == char else 0.0

    # Perceived frequency (one-hot)
    for freq in PERCEIVED_FREQUENCIES:
        if freq == "unknown":
            continue
        d[f"freq_{freq}"] = 1.0 if ctx.perceived_frequency == freq else 0.0

    # Issue duration (one-hot)
    for dur in ISSUE_DURATIONS:
        if dur == "unknown":
            continue
        d[f"dur_{dur}"] = 1.0 if ctx.issue_duration == dur else 0.0

    # Vehicle type (one-hot)
    for veh in VEHICLE_TYPES:
        if veh == "unknown":
            continue
        d[f"veh_{veh}"] = 1.0 if ctx.vehicle_type == veh else 0.0

    # Mileage (one-hot)
    mileage_map = {
        "under_50k": "mileage_under_50k",
        "50k_100k": "mileage_50k_100k",
        "100k_150k": "mileage_100k_150k",
        "over_150k": "mileage_over_150k",
    }
    for key, field_name in mileage_map.items():
        d[field_name] = 1.0 if ctx.mileage_range == key else 0.0

    # Recent maintenance (one-hot)
    for maint in RECENT_MAINTENANCE:
        if maint == "unknown":
            continue
        d[f"maint_{maint}"] = 1.0 if ctx.recent_maintenance == maint else 0.0

    return d


# ---------------------------------------------------------------------------
# Spectral feature computation (v2)
# ---------------------------------------------------------------------------

def compute_spectral_features(
    audio: np.ndarray,
    sr: int = 44100,
    n_fft: int = 4096,
    frame_length: int = 2048,
    hop_length: int = 512,
) -> dict:
    """
    Compute frequency-domain features from the audio signal.

    Returns dict with:
        spectral_centroid, spectral_bandwidth, spectral_flatness,
        harmonic_ratio, spectral_rolloff, dominant_frequency,
        spectral_centroid_std, spectral_entropy
    """
    # Compute magnitude spectrum (global)
    spectrum = np.abs(np.fft.rfft(audio, n=n_fft))
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sr)
    nyquist = sr / 2.0

    # Avoid division by zero
    total_energy = np.sum(spectrum) + 1e-10

    # --- Spectral Centroid ---
    centroid = np.sum(freqs * spectrum) / total_energy

    # --- Spectral Bandwidth ---
    bandwidth = np.sqrt(
        np.sum(((freqs - centroid) ** 2) * spectrum) / total_energy
    )

    # --- Spectral Flatness (Wiener entropy) ---
    power = spectrum ** 2 + 1e-20
    log_mean = np.mean(np.log(power))
    geometric_mean = np.exp(log_mean)
    arithmetic_mean = np.mean(power)
    flatness = geometric_mean / (arithmetic_mean + 1e-10)
    flatness = float(np.clip(flatness, 0.0, 1.0))

    # --- Harmonic Ratio ---
    harmonic_ratio = _compute_harmonic_ratio(audio, sr)

    # --- Spectral Rolloff (85th percentile) ---
    cumulative_energy = np.cumsum(spectrum ** 2)
    total_sq_energy = cumulative_energy[-1] + 1e-10
    rolloff_idx = np.searchsorted(cumulative_energy, 0.85 * total_sq_energy)
    rolloff_freq = freqs[min(rolloff_idx, len(freqs) - 1)]
    rolloff_norm = float(np.clip(rolloff_freq / nyquist, 0.0, 1.0))

    # --- Dominant Frequency ---
    dominant_idx = np.argmax(spectrum[1:]) + 1  # skip DC
    dominant_freq = freqs[dominant_idx]
    dominant_norm = float(np.clip(dominant_freq / nyquist, 0.0, 1.0))

    # --- Spectral Centroid Std (frame-wise variation) ---
    centroid_std = _compute_spectral_centroid_std(
        audio, sr, frame_length, hop_length
    )

    # --- Spectral Entropy ---
    spec_entropy = _compute_spectral_entropy(spectrum)

    # Normalize centroid and bandwidth to [0, 1] range relative to Nyquist
    centroid_norm = float(np.clip(centroid / nyquist, 0.0, 1.0))
    bandwidth_norm = float(np.clip(bandwidth / nyquist, 0.0, 1.0))

    return {
        "spectral_centroid": centroid_norm,
        "spectral_bandwidth": bandwidth_norm,
        "spectral_flatness": flatness,
        "harmonic_ratio": harmonic_ratio,
        "spectral_rolloff": rolloff_norm,
        "dominant_frequency": dominant_norm,
        "spectral_centroid_std": centroid_std,
        "spectral_entropy": spec_entropy,
    }


def _compute_spectral_centroid_std(
    audio: np.ndarray,
    sr: int,
    frame_length: int = 2048,
    hop_length: int = 512,
) -> float:
    """
    Compute the standard deviation of per-frame spectral centroid.

    Stable whine = low std, fluctuating broadband = high std.
    Normalized to [0, 1] by dividing by Nyquist.
    """
    n_frames = 1 + (len(audio) - frame_length) // hop_length
    if n_frames < 2:
        return 0.0

    nyquist = sr / 2.0
    centroids = np.zeros(n_frames)

    for i in range(n_frames):
        start = i * hop_length
        frame = audio[start:start + frame_length]
        spectrum = np.abs(np.fft.rfft(frame))
        freqs = np.fft.rfftfreq(len(frame), d=1.0 / sr)
        total = np.sum(spectrum) + 1e-10
        centroids[i] = np.sum(freqs * spectrum) / total

    std = float(np.std(centroids))
    return float(np.clip(std / nyquist, 0.0, 1.0))


def _compute_spectral_entropy(spectrum: np.ndarray) -> float:
    """
    Shannon entropy of the normalized power spectrum.

    Higher entropy = more "disordered" / complex spectral shape.
    Normalized to [0, 1] by dividing by log(N).
    """
    power = spectrum ** 2 + 1e-20
    # Normalize to probability distribution
    prob = power / np.sum(power)
    entropy = -np.sum(prob * np.log2(prob))
    # Max possible entropy = log2(N)
    max_entropy = np.log2(len(prob))
    if max_entropy <= 0:
        return 0.0
    return float(np.clip(entropy / max_entropy, 0.0, 1.0))


def _compute_harmonic_ratio(
    audio: np.ndarray,
    sr: int,
    n_fft: int = 4096,
) -> float:
    """
    Estimate the ratio of harmonic energy to total energy.

    Uses autocorrelation to find the fundamental period,
    then sums energy at integer multiples of that frequency.
    High ratio = tonal/harmonic (gear mesh, whine).
    Low ratio = noisy/broadband (bearing, hiss).
    """
    # Autocorrelation to find fundamental
    seg_len = min(len(audio), sr)
    corr = np.correlate(audio[:seg_len], audio[:seg_len], mode="full")
    corr = corr[len(corr) // 2:]

    # Ignore the zero-lag peak; find the first significant peak
    min_lag = int(sr / 8000)  # 8000 Hz max fundamental
    max_lag = int(sr / 20)     # 20 Hz min fundamental

    if max_lag >= len(corr):
        max_lag = len(corr) - 1
    if min_lag >= max_lag:
        return 0.0

    corr_segment = corr[min_lag:max_lag]
    if len(corr_segment) == 0:
        return 0.0

    peak_idx = np.argmax(corr_segment) + min_lag
    fundamental_freq = sr / peak_idx if peak_idx > 0 else 0

    if fundamental_freq < 20:
        return 0.0

    # Compute spectrum and measure energy at harmonics
    spectrum = np.abs(np.fft.rfft(audio, n=n_fft))
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sr)

    total_energy = np.sum(spectrum ** 2) + 1e-10
    harmonic_energy = 0.0

    tolerance = 5.0  # Hz
    for harmonic_n in range(1, 16):
        target_freq = fundamental_freq * harmonic_n
        if target_freq > sr / 2:
            break
        mask = np.abs(freqs - target_freq) <= tolerance
        harmonic_energy += np.sum(spectrum[mask] ** 2)

    ratio = harmonic_energy / total_energy
    return float(np.clip(ratio, 0.0, 1.0))


# ---------------------------------------------------------------------------
# Sub-band energy computation
# ---------------------------------------------------------------------------

# Band definitions (Hz)
SUB_BANDS = {
    "band_low": (20, 300),
    "band_low_mid": (300, 1000),
    "band_mid": (1000, 3000),
    "band_high_mid": (3000, 6000),
    "band_high": (6000, 8000),
}


def compute_subband_energies(
    audio: np.ndarray,
    sr: int = 44100,
    n_fft: int = 4096,
) -> dict:
    """
    Compute energy ratio in 5 frequency bands.

    Each band's energy is normalized by total energy across all bands,
    so the values represent the proportion of energy in each band [0, 1].
    """
    spectrum = np.abs(np.fft.rfft(audio, n=n_fft))
    freqs = np.fft.rfftfreq(n_fft, d=1.0 / sr)
    power = spectrum ** 2

    band_energies = {}
    for name, (low, high) in SUB_BANDS.items():
        mask = (freqs >= low) & (freqs < high)
        band_energies[name] = float(np.sum(power[mask]))

    total = sum(band_energies.values()) + 1e-10

    return {name: energy / total for name, energy in band_energies.items()}


# ---------------------------------------------------------------------------
# Temporal feature computation (v2)
# ---------------------------------------------------------------------------

def compute_temporal_features(
    audio: np.ndarray,
    sr: int = 44100,
    frame_length: int = 2048,
    hop_length: int = 512,
) -> dict:
    """
    Compute time-domain features from the audio signal.

    Returns dict with:
        rms_energy, amplitude_variance, periodicity_score,
        transient_density, crest_factor, zero_crossing_rate
    """
    # --- RMS Energy ---
    rms = float(np.sqrt(np.mean(audio ** 2)))

    # --- Amplitude Envelope ---
    envelope = _amplitude_envelope(audio, frame_length, hop_length)

    # --- Amplitude Variance ---
    amp_var = float(np.var(envelope)) if len(envelope) > 1 else 0.0

    # --- Periodicity Score ---
    periodicity = _periodicity_score(audio, sr)

    # --- Transient Density ---
    transient_dens = _transient_density(audio, sr, frame_length, hop_length)

    # --- Crest Factor ---
    peak = float(np.max(np.abs(audio)))
    crest = (peak / (rms + 1e-10))
    # Normalize: crest of 1 = 0, crest of 20+ = 1.0
    crest_norm = float(np.clip((crest - 1.0) / 19.0, 0.0, 1.0))

    # --- Zero Crossing Rate ---
    zcr = _zero_crossing_rate(audio, sr)

    return {
        "rms_energy": rms,
        "amplitude_variance": amp_var,
        "periodicity_score": periodicity,
        "transient_density": transient_dens,
        "crest_factor": crest_norm,
        "zero_crossing_rate": zcr,
    }


def _zero_crossing_rate(audio: np.ndarray, sr: int) -> float:
    """
    Compute the zero-crossing rate (sign changes per second), normalized.

    High ZCR = high frequency content.
    Normalized: 0 crossings = 0, Nyquist rate crossings = 1.
    """
    if len(audio) < 2:
        return 0.0

    signs = np.sign(audio)
    # Count sign changes (ignore zeros)
    sign_changes = np.sum(np.abs(np.diff(signs)) > 0)
    duration = len(audio) / sr

    if duration < 0.01:
        return 0.0

    crossings_per_sec = sign_changes / duration
    # Max meaningful ZCR is approximately sample_rate (Nyquist * 2)
    normalized = float(np.clip(crossings_per_sec / sr, 0.0, 1.0))

    return normalized


def _amplitude_envelope(
    audio: np.ndarray,
    frame_length: int = 2048,
    hop_length: int = 512,
) -> np.ndarray:
    """Compute the amplitude envelope (RMS per frame)."""
    n_frames = 1 + (len(audio) - frame_length) // hop_length
    if n_frames <= 0:
        return np.array([np.sqrt(np.mean(audio ** 2))])

    envelope = np.zeros(n_frames)
    for i in range(n_frames):
        start = i * hop_length
        frame = audio[start:start + frame_length]
        envelope[i] = np.sqrt(np.mean(frame ** 2))

    return envelope


def _periodicity_score(audio: np.ndarray, sr: int) -> float:
    """
    Measure how periodic/repetitive the signal is using autocorrelation.

    Returns a value between 0 (aperiodic/random) and 1 (perfectly periodic).
    """
    segment = audio[:min(len(audio), sr * 2)]

    if len(segment) < 100:
        return 0.0

    corr = np.correlate(segment, segment, mode="full")
    corr = corr[len(corr) // 2:]
    corr = corr / (corr[0] + 1e-10)

    min_lag = int(sr * 0.002)  # 2ms minimum (500 Hz max)
    max_lag = int(sr * 0.1)    # 100ms maximum (10 Hz min)
    max_lag = min(max_lag, len(corr) - 1)

    if min_lag >= max_lag:
        return 0.0

    segment_corr = corr[min_lag:max_lag]
    if len(segment_corr) == 0:
        return 0.0

    peak_value = float(np.max(segment_corr))
    return float(np.clip(peak_value, 0.0, 1.0))


def _transient_density(
    audio: np.ndarray,
    sr: int,
    frame_length: int = 2048,
    hop_length: int = 512,
) -> float:
    """
    Count impulse onsets per second.

    Uses spectral flux to detect transient events.
    Returns onsets per second, normalized to [0, 1] range.
    """
    n_frames = 1 + (len(audio) - frame_length) // hop_length
    if n_frames < 2:
        return 0.0

    energies = np.zeros(n_frames)
    for i in range(n_frames):
        start = i * hop_length
        frame = audio[start:start + frame_length]
        energies[i] = np.sum(frame ** 2)

    flux = np.diff(energies)
    flux = np.maximum(flux, 0)

    threshold = np.mean(flux) + 2.0 * np.std(flux)
    onsets = np.sum(flux > threshold)

    duration = len(audio) / sr
    if duration < 0.01:
        return 0.0

    onsets_per_sec = onsets / duration
    normalized = float(np.clip(onsets_per_sec / 50.0, 0.0, 1.0))

    return normalized
