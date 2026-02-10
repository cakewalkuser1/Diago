"""
Fingerprint Engine
Generates digital audio fingerprints using a constellation map approach,
adapted for automotive engine and mechanical sound analysis.

The algorithm:
1. Compute a spectrogram of the audio
2. Detect spectral peaks using local maximum filtering
3. Form peak pairs within a time-frequency neighborhood
4. Hash each pair into a compact integer fingerprint

This is inspired by Shazam-style fingerprinting but tuned for:
- Low-frequency engine harmonics (20-2000 Hz)
- Repetitive mechanical patterns (bearings, belts)
- Broadband noise signatures (exhaust leaks, vacuum leaks)
"""

import hashlib
from dataclasses import dataclass

import numpy as np
from scipy import signal
from scipy.ndimage import maximum_filter, minimum_filter


# --- Configuration tuned for automotive audio ---
DEFAULT_SR = 44100
DEFAULT_N_FFT = 4096          # Larger window for low-frequency resolution
DEFAULT_HOP_LENGTH = 512
PEAK_NEIGHBORHOOD_SIZE = 20   # Local max filter size (time-freq bins)
MIN_PEAK_AMPLITUDE = -60      # dB threshold to discard quiet peaks
FAN_OUT = 15                  # Number of target peaks to pair with each anchor
TARGET_TIME_RANGE = (1, 50)   # Target zone: 1-50 frames ahead of anchor
TARGET_FREQ_RANGE = 200       # Target zone: +/- 200 freq bins from anchor
FREQ_LIMIT = 8000             # Max frequency to consider (Hz)


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


def generate_fingerprint(
    audio_data: np.ndarray,
    sr: int = DEFAULT_SR,
    n_fft: int = DEFAULT_N_FFT,
    hop_length: int = DEFAULT_HOP_LENGTH,
) -> list[Fingerprint]:
    """
    Generate a list of fingerprints from audio data.

    Args:
        audio_data: Mono float32 numpy array.
        sr: Sample rate in Hz.
        n_fft: FFT window size.
        hop_length: Hop length in samples.

    Returns:
        List of Fingerprint objects (hash_value, time_offset).
    """
    if len(audio_data) == 0:
        return []

    # Step 1: Compute spectrogram
    frequencies, times, Sxx = _compute_spectrogram(
        audio_data, sr, n_fft, hop_length
    )

    # Step 2: Convert to dB
    Sxx_db = 20 * np.log10(Sxx + 1e-10)

    # Step 3: Limit frequency range
    freq_mask = frequencies <= FREQ_LIMIT
    Sxx_db = Sxx_db[freq_mask, :]
    frequencies = frequencies[freq_mask]

    # Step 4: Detect peaks
    peaks = _detect_peaks(Sxx_db, frequencies, times)

    if len(peaks) < 2:
        return []

    # Step 5: Generate hash pairs using constellation map
    fingerprints = _generate_hashes(peaks, times)

    return fingerprints


def fingerprint_to_signature(fingerprints: list[Fingerprint]) -> dict:
    """
    Aggregate fingerprint hashes into a compact signature summary.

    Args:
        fingerprints: List of Fingerprint objects.

    Returns:
        Dictionary with signature metadata:
        - 'hashes': list of (hash_value, time_offset) tuples
        - 'num_hashes': total number of hashes
        - 'hash_set': set of unique hash values (for quick comparison)
    """
    hashes = [(fp.hash_value, fp.time_offset) for fp in fingerprints]
    hash_set = set(fp.hash_value for fp in fingerprints)

    return {
        "hashes": hashes,
        "num_hashes": len(hashes),
        "hash_set": hash_set,
    }


def _compute_spectrogram(
    audio_data: np.ndarray,
    sr: int,
    n_fft: int,
    hop_length: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute STFT magnitude spectrogram."""
    frequencies, times, Zxx = signal.stft(
        audio_data,
        fs=sr,
        window="hann",
        nperseg=n_fft,
        noverlap=n_fft - hop_length,
        nfft=n_fft,
    )
    return frequencies, times, np.abs(Zxx)


def _detect_peaks(
    Sxx_db: np.ndarray,
    frequencies: np.ndarray,
    times: np.ndarray,
) -> list[PeakPoint]:
    """
    Detect spectral peaks using local maximum filtering.

    A point is a peak if it equals the local maximum in its neighborhood
    and exceeds the minimum amplitude threshold.
    """
    # Apply local maximum filter
    local_max = maximum_filter(
        Sxx_db, size=PEAK_NEIGHBORHOOD_SIZE
    )

    # Peaks are where the spectrogram equals the local max
    peaks_mask = (Sxx_db == local_max) & (Sxx_db > MIN_PEAK_AMPLITUDE)

    # Also filter out peaks that are too close to the local minimum
    # (this removes peaks in flat/silent regions)
    local_min = minimum_filter(Sxx_db, size=PEAK_NEIGHBORHOOD_SIZE)
    prominence = Sxx_db - local_min
    peaks_mask = peaks_mask & (prominence > 5)  # At least 5 dB prominent

    # Extract peak coordinates
    freq_indices, time_indices = np.where(peaks_mask)

    peaks = []
    for fi, ti in zip(freq_indices, time_indices):
        peaks.append(PeakPoint(
            freq_bin=int(fi),
            time_bin=int(ti),
            frequency=float(frequencies[fi]),
            time=float(times[ti]),
            amplitude=float(Sxx_db[fi, ti]),
        ))

    # Sort by time, then frequency
    peaks.sort(key=lambda p: (p.time_bin, p.freq_bin))

    return peaks


def _generate_hashes(
    peaks: list[PeakPoint],
    times: np.ndarray,
) -> list[Fingerprint]:
    """
    Generate fingerprint hashes by pairing anchor peaks with target peaks
    in a forward-looking time-frequency zone (constellation map).
    """
    fingerprints = []

    for i, anchor in enumerate(peaks):
        targets_found = 0

        for j in range(i + 1, len(peaks)):
            if targets_found >= FAN_OUT:
                break

            target = peaks[j]

            # Time delta (in bins)
            dt = target.time_bin - anchor.time_bin
            if dt < TARGET_TIME_RANGE[0]:
                continue
            if dt > TARGET_TIME_RANGE[1]:
                break  # Peaks are sorted by time, no more valid targets

            # Frequency delta (in bins)
            df = abs(target.freq_bin - anchor.freq_bin)
            if df > TARGET_FREQ_RANGE:
                continue

            # Generate hash from the pair
            hash_val = _compute_hash(
                anchor.freq_bin,
                target.freq_bin,
                dt,
            )

            fingerprints.append(Fingerprint(
                hash_value=hash_val,
                time_offset=anchor.time,
            ))

            targets_found += 1

    return fingerprints


def _compute_hash(freq1: int, freq2: int, delta_time: int) -> int:
    """
    Compute a compact integer hash from a peak pair.

    Combines anchor frequency, target frequency, and time delta
    into a single 32-bit integer hash.
    """
    # Pack into a string and hash
    raw = f"{freq1}|{freq2}|{delta_time}"
    h = hashlib.sha256(raw.encode()).hexdigest()[:8]
    return int(h, 16)


def compute_fingerprint_stats(fingerprints: list[Fingerprint]) -> dict:
    """
    Compute statistics about a set of fingerprints.
    Useful for diagnostics and UI display.
    """
    if not fingerprints:
        return {
            "total_hashes": 0,
            "unique_hashes": 0,
            "time_span": 0.0,
            "density": 0.0,
        }

    hash_values = [fp.hash_value for fp in fingerprints]
    time_offsets = [fp.time_offset for fp in fingerprints]

    time_span = max(time_offsets) - min(time_offsets) if time_offsets else 0

    return {
        "total_hashes": len(fingerprints),
        "unique_hashes": len(set(hash_values)),
        "time_span": time_span,
        "density": len(fingerprints) / max(time_span, 0.001),
    }
