"""
Audio Preprocessing Module
Conditions raw audio before feature extraction and fingerprinting.

Pipeline:
1. Normalize amplitude to [-1, 1]
2. Bandpass filter (20 Hz - 8000 Hz) to isolate automotive frequency range
3. Noise floor reduction via spectral gating
"""

import numpy as np
from scipy import signal as sig


def preprocess_audio(
    audio: np.ndarray,
    sr: int = 44100,
    low_hz: float = 20.0,
    high_hz: float = 8000.0,
) -> np.ndarray:
    """
    Full preprocessing pipeline for raw automotive audio.

    Args:
        audio: Mono float32 numpy array.
        sr: Sample rate in Hz.
        low_hz: Bandpass lower cutoff.
        high_hz: Bandpass upper cutoff.

    Returns:
        Conditioned audio as float32 numpy array.
    """
    if len(audio) == 0:
        return audio

    audio = normalize_amplitude(audio)
    audio = bandpass_filter(audio, low_hz, high_hz, sr)
    audio = reduce_noise_floor(audio, sr)

    return audio


def normalize_amplitude(audio: np.ndarray) -> np.ndarray:
    """
    Peak-normalize audio to [-1.0, 1.0].
    Prevents clipping and ensures consistent levels across recordings.
    """
    peak = np.max(np.abs(audio))
    if peak < 1e-10:
        return audio  # silence, don't amplify noise
    return (audio / peak).astype(np.float32)


def bandpass_filter(
    audio: np.ndarray,
    low_hz: float,
    high_hz: float,
    sr: int,
    order: int = 5,
) -> np.ndarray:
    """
    Apply a Butterworth bandpass filter.

    Isolates the automotive-relevant frequency range (20-8000 Hz),
    removing DC offset, subsonic rumble, and ultrasonic content.

    Args:
        audio: Input audio array.
        low_hz: Lower cutoff frequency (Hz).
        high_hz: Upper cutoff frequency (Hz).
        sr: Sample rate.
        order: Filter order (higher = sharper rolloff).

    Returns:
        Filtered audio.
    """
    nyquist = sr / 2.0

    # Clamp to valid range
    low = max(low_hz / nyquist, 0.001)
    high = min(high_hz / nyquist, 0.999)

    if low >= high:
        return audio

    sos = sig.butter(order, [low, high], btype="band", output="sos")
    filtered = sig.sosfiltfilt(sos, audio).astype(np.float32)

    return filtered


def reduce_noise_floor(
    audio: np.ndarray,
    sr: int,
    n_fft: int = 2048,
    hop_length: int = 512,
    noise_percentile: float = 10.0,
    reduction_strength: float = 0.8,
) -> np.ndarray:
    """
    Spectral gating noise reduction.

    Estimates the noise profile from the quietest frames of the signal,
    then subtracts it from the full spectrogram.

    Args:
        audio: Input audio.
        sr: Sample rate.
        n_fft: FFT window size.
        hop_length: Hop length.
        noise_percentile: Percentile of quietest frames to estimate noise.
        reduction_strength: How aggressively to subtract noise (0-1).

    Returns:
        Denoised audio.
    """
    if len(audio) < n_fft:
        return audio

    # Compute STFT
    frequencies, times, Zxx = sig.stft(
        audio, fs=sr, nperseg=n_fft,
        noverlap=n_fft - hop_length, window="hann",
    )

    magnitude = np.abs(Zxx)
    phase = np.angle(Zxx)

    # Estimate noise profile from the quietest frames
    frame_energies = np.sum(magnitude ** 2, axis=0)
    threshold = np.percentile(frame_energies, noise_percentile)
    noise_frames = magnitude[:, frame_energies <= threshold]

    if noise_frames.shape[1] == 0:
        # No clearly quiet frames; use the overall minimum
        noise_profile = np.min(magnitude, axis=1, keepdims=True)
    else:
        noise_profile = np.mean(noise_frames, axis=1, keepdims=True)

    # Spectral subtraction
    cleaned_magnitude = magnitude - (reduction_strength * noise_profile)
    cleaned_magnitude = np.maximum(cleaned_magnitude, 0.0)

    # Reconstruct
    cleaned_Zxx = cleaned_magnitude * np.exp(1j * phase)
    _, cleaned_audio = sig.istft(
        cleaned_Zxx, fs=sr, nperseg=n_fft,
        noverlap=n_fft - hop_length, window="hann",
    )

    # Trim or pad to match original length
    if len(cleaned_audio) > len(audio):
        cleaned_audio = cleaned_audio[:len(audio)]
    elif len(cleaned_audio) < len(audio):
        cleaned_audio = np.pad(
            cleaned_audio, (0, len(audio) - len(cleaned_audio))
        )

    return cleaned_audio.astype(np.float32)
