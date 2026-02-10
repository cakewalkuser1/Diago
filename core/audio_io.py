"""
Audio I/O Module
Handles microphone recording and audio file loading/saving.
All audio is internally represented as mono float32 numpy arrays at 44100 Hz.
"""

import numpy as np
import sounddevice as sd
import soundfile as sf
from pathlib import Path


# Standard sample rate for all internal processing
STANDARD_SR = 44100


class AudioRecorder:
    """Handles real-time microphone recording in a non-blocking manner."""

    def __init__(self, sample_rate: int = STANDARD_SR):
        self.sample_rate = sample_rate
        self._recording = False
        self._frames: list[np.ndarray] = []
        self._stream = None

    @property
    def is_recording(self) -> bool:
        return self._recording

    def start_recording(self):
        """Start recording from the default microphone."""
        if self._recording:
            return

        self._frames = []
        self._recording = True

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype="float32",
            callback=self._audio_callback,
            blocksize=1024,
        )
        self._stream.start()

    def stop_recording(self) -> np.ndarray:
        """Stop recording and return the captured audio as a numpy array."""
        if not self._recording:
            return np.array([], dtype=np.float32)

        self._recording = False

        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if not self._frames:
            return np.array([], dtype=np.float32)

        audio_data = np.concatenate(self._frames, axis=0).flatten()
        return audio_data

    def get_current_buffer(self) -> np.ndarray:
        """Return the audio recorded so far (for real-time preview)."""
        if not self._frames:
            return np.array([], dtype=np.float32)
        return np.concatenate(self._frames, axis=0).flatten()

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback for the audio input stream."""
        if self._recording:
            self._frames.append(indata.copy())


def record_audio(duration: float, sample_rate: int = STANDARD_SR) -> np.ndarray:
    """
    Record audio from the default microphone for a fixed duration.

    Args:
        duration: Recording duration in seconds.
        sample_rate: Sample rate in Hz (default 44100).

    Returns:
        Mono float32 numpy array of the recorded audio.
    """
    audio = sd.rec(
        int(duration * sample_rate),
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
    )
    sd.wait()
    return audio.flatten()


def load_audio_file(path: str) -> tuple[np.ndarray, int]:
    """
    Load an audio file and normalize to mono float32 at the standard sample rate.

    Supports WAV, FLAC, OGG natively via soundfile.
    MP3 files are handled via pydub (requires ffmpeg).

    Args:
        path: Path to the audio file.

    Returns:
        Tuple of (audio_data as mono float32 numpy array, sample_rate).

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the file format is not supported.
    """
    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"Audio file not found: {path}")

    extension = file_path.suffix.lower()

    if extension == ".mp3":
        return _load_mp3(path)
    elif extension in (".wav", ".flac", ".ogg"):
        return _load_soundfile(path)
    else:
        raise ValueError(
            f"Unsupported audio format: {extension}. "
            "Supported: .wav, .mp3, .flac, .ogg"
        )


def _load_soundfile(path: str) -> tuple[np.ndarray, int]:
    """Load audio using soundfile (WAV, FLAC, OGG)."""
    audio_data, sr = sf.read(path, dtype="float32")

    # Convert stereo to mono if needed
    if audio_data.ndim > 1:
        audio_data = np.mean(audio_data, axis=1)

    # Resample if not at standard rate
    if sr != STANDARD_SR:
        audio_data = _resample(audio_data, sr, STANDARD_SR)
        sr = STANDARD_SR

    return audio_data, sr


def _load_mp3(path: str) -> tuple[np.ndarray, int]:
    """Load MP3 audio using pydub (requires ffmpeg)."""
    try:
        from pydub import AudioSegment
    except ImportError:
        raise ImportError(
            "pydub is required for MP3 support. Install it with: pip install pydub"
        )

    audio_segment = AudioSegment.from_mp3(path)

    # Convert to mono
    if audio_segment.channels > 1:
        audio_segment = audio_segment.set_channels(1)

    # Convert to standard sample rate
    if audio_segment.frame_rate != STANDARD_SR:
        audio_segment = audio_segment.set_frame_rate(STANDARD_SR)

    # Convert to numpy float32 array
    samples = np.array(audio_segment.get_array_of_samples(), dtype=np.float32)

    # Normalize to [-1.0, 1.0]
    max_val = float(2 ** (audio_segment.sample_width * 8 - 1))
    samples = samples / max_val

    return samples, STANDARD_SR


def _resample(audio_data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Resample audio data to the target sample rate using linear interpolation."""
    if orig_sr == target_sr:
        return audio_data

    duration = len(audio_data) / orig_sr
    target_length = int(duration * target_sr)
    indices = np.linspace(0, len(audio_data) - 1, target_length)
    resampled = np.interp(indices, np.arange(len(audio_data)), audio_data)
    return resampled.astype(np.float32)


def save_audio(data: np.ndarray, path: str, sample_rate: int = STANDARD_SR):
    """
    Save audio data to a WAV file.

    Args:
        data: Mono float32 numpy array.
        path: Output file path.
        sample_rate: Sample rate in Hz.
    """
    sf.write(path, data, sample_rate)


def get_audio_duration(data: np.ndarray, sample_rate: int = STANDARD_SR) -> float:
    """Calculate the duration of audio data in seconds."""
    return len(data) / sample_rate


def get_available_devices() -> list[dict]:
    """Return a list of available audio input devices."""
    devices = sd.query_devices()
    input_devices = []
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            input_devices.append({
                "index": i,
                "name": dev["name"],
                "channels": dev["max_input_channels"],
                "sample_rate": dev["default_samplerate"],
            })
    return input_devices
