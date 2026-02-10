"""
Spectrogram Engine
Computes STFT and Mel spectrograms from audio data, with plotting support
for embedding in the PyQt6 GUI via matplotlib.

Tuned for automotive audio analysis:
- Frequency range: 20 Hz - 8000 Hz
- Larger FFT windows (2048-4096) for low-frequency engine harmonics
"""

import numpy as np
from scipy import signal
from matplotlib.figure import Figure
from matplotlib.axes import Axes


def compute_spectrogram(
    audio_data: np.ndarray,
    sr: int = 44100,
    n_fft: int = 2048,
    hop_length: int = 512,
    window: str = "hann",
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute the Short-Time Fourier Transform (STFT) magnitude spectrogram.

    Args:
        audio_data: Mono float32 numpy array.
        sr: Sample rate in Hz.
        n_fft: FFT window size (larger = better frequency resolution).
        hop_length: Number of samples between successive frames.
        window: Window function name.

    Returns:
        Tuple of (frequencies, times, spectrogram_magnitude).
        - frequencies: 1D array of frequency bins (Hz)
        - times: 1D array of time frames (seconds)
        - Sxx: 2D magnitude spectrogram (frequencies x times)
    """
    frequencies, times, Zxx = signal.stft(
        audio_data,
        fs=sr,
        window=window,
        nperseg=n_fft,
        noverlap=n_fft - hop_length,
        nfft=n_fft,
    )

    # Magnitude spectrogram
    Sxx = np.abs(Zxx)

    return frequencies, times, Sxx


def compute_power_spectrogram(
    audio_data: np.ndarray,
    sr: int = 44100,
    n_fft: int = 2048,
    hop_length: int = 512,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute the power spectrogram in decibels.

    Returns:
        Tuple of (frequencies, times, Sxx_db) where Sxx_db is in decibels.
    """
    frequencies, times, Sxx = compute_spectrogram(
        audio_data, sr, n_fft, hop_length
    )

    # Convert to power (dB), with floor to avoid log(0)
    Sxx_db = 20 * np.log10(Sxx + 1e-10)

    return frequencies, times, Sxx_db


def compute_mel_spectrogram(
    audio_data: np.ndarray,
    sr: int = 44100,
    n_fft: int = 2048,
    hop_length: int = 512,
    n_mels: int = 128,
    fmin: float = 20.0,
    fmax: float = 8000.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Compute a Mel-scaled spectrogram.
    Mel scaling better represents how humans perceive pitch,
    which is useful for identifying engine harmonic patterns.

    Args:
        audio_data: Mono float32 numpy array.
        sr: Sample rate in Hz.
        n_fft: FFT window size.
        hop_length: Hop length in samples.
        n_mels: Number of Mel bands.
        fmin: Minimum frequency (Hz).
        fmax: Maximum frequency (Hz).

    Returns:
        Tuple of (mel_frequencies, times, mel_spectrogram).
    """
    # First compute the standard STFT
    frequencies, times, Sxx = compute_spectrogram(
        audio_data, sr, n_fft, hop_length
    )

    # Build a Mel filter bank
    mel_filters = _create_mel_filterbank(
        n_mels, n_fft, sr, fmin, fmax
    )

    # Apply filter bank to power spectrogram
    Sxx_power = Sxx ** 2
    mel_spec = mel_filters @ Sxx_power

    # Convert to dB
    mel_spec_db = 10 * np.log10(mel_spec + 1e-10)

    # Mel frequency centers
    mel_freqs = _mel_frequencies(n_mels, fmin, fmax)

    return mel_freqs, times, mel_spec_db


def _hz_to_mel(hz: float) -> float:
    """Convert frequency in Hz to Mel scale."""
    return 2595.0 * np.log10(1.0 + hz / 700.0)


def _mel_to_hz(mel: float) -> float:
    """Convert Mel scale to frequency in Hz."""
    return 700.0 * (10.0 ** (mel / 2595.0) - 1.0)


def _mel_frequencies(n_mels: int, fmin: float, fmax: float) -> np.ndarray:
    """Generate center frequencies for Mel bands."""
    mel_min = _hz_to_mel(fmin)
    mel_max = _hz_to_mel(fmax)
    mels = np.linspace(mel_min, mel_max, n_mels)
    return np.array([_mel_to_hz(m) for m in mels])


def _create_mel_filterbank(
    n_mels: int,
    n_fft: int,
    sr: int,
    fmin: float,
    fmax: float,
) -> np.ndarray:
    """
    Create a Mel filter bank matrix.

    Returns:
        2D array of shape (n_mels, n_fft // 2 + 1).
    """
    n_freqs = n_fft // 2 + 1

    # Mel scale boundaries
    mel_min = _hz_to_mel(fmin)
    mel_max = _hz_to_mel(fmax)

    # n_mels + 2 points (including edges)
    mel_points = np.linspace(mel_min, mel_max, n_mels + 2)
    hz_points = np.array([_mel_to_hz(m) for m in mel_points])

    # Convert Hz to FFT bin indices
    bin_points = np.floor((n_fft + 1) * hz_points / sr).astype(int)

    # Build triangular filters
    filterbank = np.zeros((n_mels, n_freqs))

    for i in range(n_mels):
        left = bin_points[i]
        center = bin_points[i + 1]
        right = bin_points[i + 2]

        # Rising slope
        for j in range(left, center):
            if j < n_freqs and center > left:
                filterbank[i, j] = (j - left) / (center - left)

        # Falling slope
        for j in range(center, right):
            if j < n_freqs and right > center:
                filterbank[i, j] = (right - j) / (right - center)

    return filterbank


def plot_spectrogram(
    frequencies: np.ndarray,
    times: np.ndarray,
    Sxx: np.ndarray,
    ax: Axes,
    title: str = "Spectrogram",
    freq_limit: float = 8000.0,
    colorbar: bool = True,
    cmap: str = "magma",
) -> None:
    """
    Render a spectrogram onto a matplotlib Axes for GUI embedding.

    Args:
        frequencies: 1D array of frequency bins.
        times: 1D array of time frames.
        Sxx: 2D spectrogram data (frequencies x times).
        ax: Matplotlib Axes to draw on.
        title: Plot title.
        freq_limit: Maximum frequency to display (Hz).
        colorbar: Whether to add a colorbar.
        cmap: Colormap name.
    """
    ax.clear()

    # Limit frequency range
    freq_mask = frequencies <= freq_limit
    Sxx_display = Sxx[freq_mask, :]
    freqs_display = frequencies[freq_mask]

    # Plot
    mesh = ax.pcolormesh(
        times,
        freqs_display,
        Sxx_display,
        shading="gouraud",
        cmap=cmap,
    )

    ax.set_ylabel("Frequency (Hz)", color="#cdd6f4", fontsize=10)
    ax.set_xlabel("Time (s)", color="#cdd6f4", fontsize=10)
    ax.set_title(title, color="#cdd6f4", fontsize=12, fontweight="bold")

    # Style for dark theme
    ax.set_facecolor("#1e1e2e")
    ax.tick_params(colors="#a6adc8", labelsize=8)
    ax.spines["bottom"].set_color("#45475a")
    ax.spines["top"].set_color("#45475a")
    ax.spines["left"].set_color("#45475a")
    ax.spines["right"].set_color("#45475a")

    if colorbar:
        cb = ax.figure.colorbar(mesh, ax=ax, pad=0.02)
        cb.ax.tick_params(colors="#a6adc8", labelsize=8)
        cb.set_label("Amplitude (dB)", color="#cdd6f4", fontsize=9)


def plot_waveform(
    audio_data: np.ndarray,
    sr: int,
    ax: Axes,
    title: str = "Waveform",
) -> None:
    """
    Plot the audio waveform on a matplotlib Axes.

    Args:
        audio_data: Mono float32 numpy array.
        sr: Sample rate.
        ax: Matplotlib Axes.
        title: Plot title.
    """
    ax.clear()

    time_axis = np.arange(len(audio_data)) / sr
    ax.plot(time_axis, audio_data, color="#89b4fa", linewidth=0.5, alpha=0.8)

    ax.set_ylabel("Amplitude", color="#cdd6f4", fontsize=10)
    ax.set_xlabel("Time (s)", color="#cdd6f4", fontsize=10)
    ax.set_title(title, color="#cdd6f4", fontsize=12, fontweight="bold")
    ax.set_ylim(-1.0, 1.0)

    # Dark theme styling
    ax.set_facecolor("#1e1e2e")
    ax.tick_params(colors="#a6adc8", labelsize=8)
    ax.spines["bottom"].set_color("#45475a")
    ax.spines["top"].set_color("#45475a")
    ax.spines["left"].set_color("#45475a")
    ax.spines["right"].set_color("#45475a")
    ax.grid(True, alpha=0.15, color="#585b70")
