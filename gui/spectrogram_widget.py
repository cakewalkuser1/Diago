"""
Spectrogram Visualization Widget
Embeds a matplotlib figure in PyQt6 for displaying spectrograms and waveforms.
"""

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSizePolicy

from core.spectrogram import (
    compute_power_spectrogram,
    compute_mel_spectrogram,
    plot_spectrogram,
    plot_waveform,
)


class SpectrogramWidget(QWidget):
    """
    Widget that displays spectrogram and waveform plots.
    Uses matplotlib embedded in PyQt6 via FigureCanvasQTAgg.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._setup_figure()
        self._setup_layout()

        # Store current data for mode switching
        self._current_audio = None
        self._current_sr = None
        self._display_mode = "spectrogram"  # or "mel", "waveform"

    def _setup_figure(self):
        """Create the matplotlib figure with dark theme."""
        self.figure = Figure(figsize=(10, 4), dpi=100)
        self.figure.set_facecolor("#1e1e2e")

        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        # Create a single axes for the main plot
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor("#1e1e2e")
        self._show_placeholder()

    def _setup_layout(self):
        """Set up the widget layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

    def _show_placeholder(self):
        """Show a placeholder message when no audio is loaded."""
        self.ax.clear()
        self.ax.set_facecolor("#1e1e2e")
        self.ax.text(
            0.5, 0.5,
            "Record or import audio to view spectrogram",
            transform=self.ax.transAxes,
            ha="center", va="center",
            fontsize=14, color="#585b70",
            style="italic",
        )
        self.ax.set_xticks([])
        self.ax.set_yticks([])
        for spine in self.ax.spines.values():
            spine.set_color("#45475a")
        self.figure.tight_layout()
        self.canvas.draw()

    def display_spectrogram(
        self,
        audio_data: np.ndarray,
        sr: int = 44100,
        mode: str = "spectrogram",
    ):
        """
        Compute and display a spectrogram of the given audio data.

        Args:
            audio_data: Mono float32 numpy array.
            sr: Sample rate.
            mode: 'spectrogram', 'mel', or 'waveform'.
        """
        self._current_audio = audio_data
        self._current_sr = sr
        self._display_mode = mode

        # Clear any existing colorbars
        self.figure.clear()
        self.ax = self.figure.add_subplot(111)

        if mode == "waveform":
            plot_waveform(audio_data, sr, self.ax, title="Audio Waveform")
        elif mode == "mel":
            mel_freqs, times, mel_spec = compute_mel_spectrogram(
                audio_data, sr
            )
            plot_spectrogram(
                mel_freqs, times, mel_spec, self.ax,
                title="Mel Spectrogram",
                freq_limit=8000,
                cmap="magma",
            )
        else:
            # Standard STFT power spectrogram
            frequencies, times, Sxx_db = compute_power_spectrogram(
                audio_data, sr
            )
            plot_spectrogram(
                frequencies, times, Sxx_db, self.ax,
                title="Power Spectrogram (dB)",
                freq_limit=8000,
                cmap="magma",
            )

        self.figure.tight_layout()
        self.canvas.draw()

    def switch_mode(self, mode: str):
        """Switch display mode and refresh if audio is loaded."""
        if self._current_audio is not None and self._current_sr is not None:
            self.display_spectrogram(
                self._current_audio, self._current_sr, mode
            )

    def clear(self):
        """Clear the display and show placeholder."""
        self._current_audio = None
        self._current_sr = None
        self.figure.clear()
        self.ax = self.figure.add_subplot(111)
        self._show_placeholder()

    def update_waveform_realtime(self, audio_data: np.ndarray, sr: int = 44100):
        """
        Lightweight waveform update for real-time recording preview.
        Only redraws the waveform without full spectrogram computation.
        """
        self.figure.clear()
        self.ax = self.figure.add_subplot(111)
        plot_waveform(audio_data, sr, self.ax, title="Recording...")
        self.figure.tight_layout()
        self.canvas.draw_idle()

    @property
    def has_audio(self) -> bool:
        """Check if audio data is currently loaded."""
        return self._current_audio is not None

    @property
    def current_audio(self) -> np.ndarray | None:
        return self._current_audio

    @property
    def current_sr(self) -> int | None:
        return self._current_sr
