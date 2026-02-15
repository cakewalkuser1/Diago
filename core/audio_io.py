"""
Audio I/O Module
Handles microphone recording and audio file loading/saving.
All audio is internally represented as mono float32 numpy arrays at 44100 Hz.
Supports WAV, MP3, MP4 (audio track), FLAC, OGG.
"""

import io
import logging
import os
import shutil
from pathlib import Path

import numpy as np
import sounddevice as sd
import soundfile as sf

from core.config import get_settings

logger = logging.getLogger(__name__)

# Standard sample rate for all internal processing
STANDARD_SR = 44100

# Extensions supported by soundfile (from bytes)
_SOUNDFILE_EXTENSIONS = {".wav", ".flac", ".ogg", ".webm"}
# Extensions supported by pydub (MP3, MP4 / M4A)
_PYDUB_EXTENSIONS = {".mp3", ".mp4", ".m4a"}

# Set once so we add ffmpeg to PATH before pydub is ever imported (avoids pydub's which() warnings).
_ffmpeg_path_prepared = False


def _find_ffmpeg_bin() -> tuple[str | None, str | None]:
    """Return (ffmpeg_path, ffprobe_path). Checks PATH then WinGet / common Windows locations."""
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg and ffprobe:
        return ffmpeg, ffprobe
    # Windows: WinGet Gyan.FFmpeg and any folder containing ffmpeg.exe + ffprobe.exe
    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        base = Path(local) / "Microsoft" / "WinGet" / "Packages"
        if base.exists():
            for d in base.iterdir():
                if not d.is_dir():
                    continue
                # Gyan.FFmpeg* or search any package for ffmpeg-*/bin
                for sub in d.glob("ffmpeg-*"):
                    if sub.is_dir():
                        bin_dir = sub / "bin"
                        fm = bin_dir / "ffmpeg.exe"
                        fp = bin_dir / "ffprobe.exe"
                        if fm.exists() and fp.exists():
                            return str(fm), str(fp)
    # ProgramFiles fallback (e.g. chocolatey or manual install)
    for root in [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")]:
        if not root:
            continue
        for d in Path(root).glob("ffmpeg*/bin"):
            if d.is_dir():
                fm, fp = d / "ffmpeg.exe", d / "ffprobe.exe"
                if fm.exists() and fp.exists():
                    return str(fm), str(fp)
    return None, None


def _ensure_pydub_ffmpeg() -> None:
    """Add ffmpeg to PATH before importing pydub (so which() finds it), then set full paths on AudioSegment."""
    global _ffmpeg_path_prepared
    ffmpeg_path, ffprobe_path = _find_ffmpeg_bin()
    if ffmpeg_path:
        bin_dir = str(Path(ffmpeg_path).parent)
        if not _ffmpeg_path_prepared:
            os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
            _ffmpeg_path_prepared = True
            logger.debug("Prepending ffmpeg to PATH: %s", bin_dir)
    # Import only after PATH is set so pydub's get_encoder_name() / get_prober_name() find ffmpeg
    from pydub import AudioSegment  # noqa: E402
    if getattr(AudioSegment, "_diago_ffmpeg_set", False):
        return
    if ffmpeg_path:
        AudioSegment.converter = ffmpeg_path
        if ffprobe_path:
            AudioSegment.ffprobe = ffprobe_path
    else:
        logger.warning("ffmpeg/ffprobe not found; MP3/MP4 import may fail. Install FFmpeg and add to PATH.")
    AudioSegment._diago_ffmpeg_set = True


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

    Supports WAV, FLAC, OGG via soundfile; MP3 and MP4 (audio track) via pydub (requires ffmpeg).

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
    elif extension in (".mp4", ".m4a"):
        return _load_mp4(path)
    elif extension in (".wav", ".flac", ".ogg"):
        return _load_soundfile(path)
    else:
        raise ValueError(
            f"Unsupported audio format: {extension}. "
            "Supported: .wav, .mp3, .mp4, .m4a, .flac, .ogg"
        )


def load_audio_bytes(audio_bytes: bytes, filename: str = "") -> tuple[np.ndarray, int]:
    """
    Load audio from in-memory bytes and normalize to mono float32 at STANDARD_SR.

    Supports WAV, MP3, MP4 (audio), FLAC, OGG, WEBM. Uses filename extension to detect format.

    Args:
        audio_bytes: Raw file bytes.
        filename: Original filename (e.g. "recording.mp4") for format detection.

    Returns:
        Tuple of (audio_data as mono float32 numpy array, sample_rate).

    Raises:
        ValueError: If format is unsupported or decoding fails.
    """
    extension = (Path(filename).suffix.lower() if filename else "") or ".wav"

    if extension in _SOUNDFILE_EXTENSIONS:
        try:
            data, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
            if data.ndim > 1:
                data = np.mean(data, axis=1)
            if sr != STANDARD_SR:
                data = _resample(data, sr, STANDARD_SR)
                sr = STANDARD_SR
            return data.astype(np.float32), sr
        except Exception as e:
            raise ValueError(f"Could not decode {extension} audio: {e}") from e

    if extension in _PYDUB_EXTENSIONS:
        return _load_pydub_bytes(audio_bytes, extension)

    # Try soundfile first, then pydub
    try:
        data, sr = sf.read(io.BytesIO(audio_bytes), dtype="float32")
        if data.ndim > 1:
            data = np.mean(data, axis=1)
        if sr != STANDARD_SR:
            data = _resample(data, sr, STANDARD_SR)
            sr = STANDARD_SR
        return data.astype(np.float32), sr
    except Exception:
        pass
    for fmt in (".mp3", ".mp4"):
        try:
            return _load_pydub_bytes(audio_bytes, fmt)
        except Exception:
            continue
    raise ValueError(
        f"Unsupported or invalid audio format (filename: {filename}). "
        "Supported: .wav, .mp3, .mp4, .m4a, .flac, .ogg, .webm"
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
    return _load_pydub_file(path, "mp3")


def _load_mp4(path: str) -> tuple[np.ndarray, int]:
    """Load MP4/M4A audio track using pydub (requires ffmpeg)."""
    return _load_pydub_file(path, "mp4")


def _load_pydub_file(path: str, format: str) -> tuple[np.ndarray, int]:
    """Load audio from file using pydub (MP3, MP4, etc.)."""
    try:
        from pydub import AudioSegment
    except ImportError:
        raise ImportError(
            "pydub is required for MP3/MP4 support. Install it with: pip install pydub"
        )
    _ensure_pydub_ffmpeg()
    if format == "mp3":
        segment = AudioSegment.from_mp3(path)
    else:
        segment = AudioSegment.from_file(path, format=format)
    return _pydub_to_mono_float32(segment)


def _load_pydub_bytes(audio_bytes: bytes, extension: str) -> tuple[np.ndarray, int]:
    """Load audio from bytes using pydub. extension e.g. .mp3, .mp4."""
    try:
        from pydub import AudioSegment
    except ImportError:
        raise ImportError(
            "pydub is required for MP3/MP4 support. Install it with: pip install pydub"
        )
    _ensure_pydub_ffmpeg()
    fmt = extension.lstrip(".").lower() or "mp3"
    with io.BytesIO(audio_bytes) as f:
        segment = AudioSegment.from_file(f, format=fmt)
    return _pydub_to_mono_float32(segment)


def _pydub_to_mono_float32(segment) -> tuple[np.ndarray, int]:
    """Convert a pydub AudioSegment to mono float32 numpy at STANDARD_SR."""
    if segment.channels > 1:
        segment = segment.set_channels(1)
    if segment.frame_rate != STANDARD_SR:
        segment = segment.set_frame_rate(STANDARD_SR)
    samples = np.array(segment.get_array_of_samples(), dtype=np.float32)
    max_val = float(2 ** (segment.sample_width * 8 - 1))
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
