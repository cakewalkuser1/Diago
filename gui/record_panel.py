"""
Recording and Import Panel
Provides controls for microphone recording and audio file importing.
Includes real-time waveform preview during recording.
"""

import os

import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
    QComboBox, QLabel, QFileDialog, QSizePolicy,
)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer

from core.audio_io import AudioRecorder, load_audio_file, save_audio, STANDARD_SR


class RecordingThread(QThread):
    """Thread for non-blocking audio recording."""
    audio_chunk = pyqtSignal(np.ndarray)  # Emitted periodically with buffer
    finished_recording = pyqtSignal(np.ndarray)  # Emitted when recording stops

    def __init__(self, recorder: AudioRecorder, parent=None):
        super().__init__(parent)
        self._recorder = recorder
        self._running = False

    def run(self):
        """Start recording in the background."""
        self._running = True
        self._recorder.start_recording()

        # Poll for audio chunks while recording
        while self._running and self._recorder.is_recording:
            self.msleep(200)  # Update interval: 200ms
            buffer = self._recorder.get_current_buffer()
            if len(buffer) > 0:
                self.audio_chunk.emit(buffer)

    def stop(self):
        """Stop recording and emit the final audio."""
        self._running = False
        audio = self._recorder.stop_recording()
        self.finished_recording.emit(audio)


class RecordPanel(QWidget):
    """
    Panel with recording controls and file import functionality.

    Signals:
        audio_loaded: Emitted when audio data is ready (from recording or file).
                      Carries (audio_data: np.ndarray, sample_rate: int).
        recording_update: Emitted periodically during recording with the current buffer.
    """
    audio_loaded = pyqtSignal(np.ndarray, int)
    recording_update = pyqtSignal(np.ndarray)
    status_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._recorder = AudioRecorder(sample_rate=STANDARD_SR)
        self._recording_thread = None
        self._current_audio = None
        self._current_sr = STANDARD_SR

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Build the recording panel UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(10)

        # Record button
        self.record_btn = QPushButton("Record")
        self.record_btn.setObjectName("recordBtn")
        self.record_btn.setMinimumWidth(100)
        self.record_btn.setToolTip("Start recording from microphone")
        layout.addWidget(self.record_btn)

        # Stop button
        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setObjectName("stopBtn")
        self.stop_btn.setMinimumWidth(80)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setToolTip("Stop recording")
        layout.addWidget(self.stop_btn)

        # Import button
        self.import_btn = QPushButton("Import File")
        self.import_btn.setMinimumWidth(100)
        self.import_btn.setToolTip("Load an audio file (WAV, MP3, FLAC, OGG)")
        layout.addWidget(self.import_btn)

        # Separator
        separator = QLabel("|")
        separator.setStyleSheet("color: #45475a; font-size: 16px;")
        layout.addWidget(separator)

        # Duration selector for timed recording
        duration_label = QLabel("Duration:")
        layout.addWidget(duration_label)

        self.duration_combo = QComboBox()
        self.duration_combo.addItems([
            "Manual", "3s", "5s", "10s", "15s", "30s", "60s"
        ])
        self.duration_combo.setCurrentIndex(2)  # Default: 5s
        self.duration_combo.setMinimumWidth(80)
        self.duration_combo.setToolTip(
            "Recording duration (Manual = stop manually)"
        )
        layout.addWidget(self.duration_combo)

        # Separator
        separator2 = QLabel("|")
        separator2.setStyleSheet("color: #45475a; font-size: 16px;")
        layout.addWidget(separator2)

        # View mode selector
        view_label = QLabel("View:")
        layout.addWidget(view_label)

        self.view_combo = QComboBox()
        self.view_combo.addItems(["Spectrogram", "Mel Spectrogram", "Waveform"])
        self.view_combo.setMinimumWidth(130)
        self.view_combo.setToolTip("Spectrogram display mode")
        layout.addWidget(self.view_combo)

        # Spacer
        layout.addStretch()

        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #a6adc8; font-style: italic;")
        layout.addWidget(self.status_label)

    def _connect_signals(self):
        """Connect button signals to handlers."""
        self.record_btn.clicked.connect(self._start_recording)
        self.stop_btn.clicked.connect(self._stop_recording)
        self.import_btn.clicked.connect(self._import_file)

    def _start_recording(self):
        """Start microphone recording."""
        self.record_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.import_btn.setEnabled(False)
        self.status_label.setText("Recording...")
        self.status_label.setStyleSheet("color: #a6e3a1; font-style: italic;")

        self._recording_thread = RecordingThread(self._recorder)
        self._recording_thread.audio_chunk.connect(self._on_audio_chunk)
        self._recording_thread.finished_recording.connect(
            self._on_recording_finished
        )
        self._recording_thread.start()

        # Set up auto-stop timer if a duration is selected
        duration_text = self.duration_combo.currentText()
        if duration_text != "Manual":
            duration_seconds = int(duration_text.replace("s", ""))
            self._auto_stop_timer = QTimer()
            self._auto_stop_timer.setSingleShot(True)
            self._auto_stop_timer.timeout.connect(self._stop_recording)
            self._auto_stop_timer.start(duration_seconds * 1000)

        self.status_message.emit("Recording started...")

    def _stop_recording(self):
        """Stop the current recording."""
        if self._recording_thread is not None and self._recording_thread.isRunning():
            self._recording_thread.stop()
            self._recording_thread.wait(5000)
            self._recording_thread = None

        # Stop auto-stop timer if running
        if hasattr(self, "_auto_stop_timer"):
            self._auto_stop_timer.stop()

        self.record_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.import_btn.setEnabled(True)

    def _on_audio_chunk(self, buffer: np.ndarray):
        """Handle periodic audio buffer updates during recording."""
        self.recording_update.emit(buffer)
        duration = len(buffer) / STANDARD_SR
        self.status_label.setText(f"Recording... {duration:.1f}s")

    def _on_recording_finished(self, audio_data: np.ndarray):
        """Handle completed recording."""
        if len(audio_data) == 0:
            self.status_label.setText("Recording empty")
            self.status_label.setStyleSheet(
                "color: #f38ba8; font-style: italic;"
            )
            self.status_message.emit("Recording was empty.")
            return

        self._current_audio = audio_data
        self._current_sr = STANDARD_SR
        duration = len(audio_data) / STANDARD_SR

        self.status_label.setText(
            f"Recorded {duration:.1f}s ({len(audio_data)} samples)"
        )
        self.status_label.setStyleSheet("color: #a6e3a1; font-style: italic;")

        self.audio_loaded.emit(audio_data, STANDARD_SR)
        self.status_message.emit(
            f"Recording complete: {duration:.1f}s"
        )

    def _import_file(self):
        """Open a file dialog to import an audio file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Audio File",
            "",
            "Audio Files (*.wav *.mp3 *.flac *.ogg);;All Files (*)",
        )

        if not file_path:
            return

        self.status_label.setText("Loading...")
        self.status_label.setStyleSheet("color: #f9e2af; font-style: italic;")

        try:
            audio_data, sr = load_audio_file(file_path)
            self._current_audio = audio_data
            self._current_sr = sr

            duration = len(audio_data) / sr
            filename = os.path.basename(file_path)

            self.status_label.setText(
                f"Loaded: {filename} ({duration:.1f}s)"
            )
            self.status_label.setStyleSheet(
                "color: #a6e3a1; font-style: italic;"
            )

            self.audio_loaded.emit(audio_data, sr)
            self.status_message.emit(
                f"Loaded {filename} ({duration:.1f}s, {sr} Hz)"
            )

        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            self.status_label.setStyleSheet(
                "color: #f38ba8; font-style: italic;"
            )
            self.status_message.emit(f"Error loading file: {str(e)}")

    def save_current_audio(self, path: str) -> bool:
        """Save the current audio buffer to a WAV file."""
        if self._current_audio is None:
            return False
        try:
            save_audio(self._current_audio, path, self._current_sr)
            return True
        except Exception:
            return False

    @property
    def current_view_mode(self) -> str:
        """Get the current spectrogram view mode."""
        mode_map = {
            "Spectrogram": "spectrogram",
            "Mel Spectrogram": "mel",
            "Waveform": "waveform",
        }
        return mode_map.get(self.view_combo.currentText(), "spectrogram")
