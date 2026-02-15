"""
Audio API Routes
Endpoints for audio file upload, spectrogram generation, etc.
"""

import base64
import io
import logging

import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Response Models
# ---------------------------------------------------------------------------

class SpectrogramResponse(BaseModel):
    """Spectrogram data as base64-encoded PNG or raw arrays."""
    image_base64: str  # Base64 PNG
    duration_seconds: float
    sample_rate: int


class AudioInfoResponse(BaseModel):
    """Basic info about an uploaded audio file."""
    duration_seconds: float
    sample_rate: int
    num_samples: int
    peak_amplitude: float
    rms_energy: float


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/info", response_model=AudioInfoResponse)
async def get_audio_info(audio_file: UploadFile = File(...)):
    """Get basic information about an uploaded audio file (WAV, MP3, MP4, FLAC, OGG, WEBM)."""
    try:
        from core.audio_io import load_audio_bytes
        audio_bytes = await audio_file.read()
        filename = getattr(audio_file, "filename", None) or "audio"
        audio_data, sr = load_audio_bytes(audio_bytes, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid audio file: {e}")

    return AudioInfoResponse(
        duration_seconds=len(audio_data) / sr,
        sample_rate=sr,
        num_samples=len(audio_data),
        peak_amplitude=float(np.max(np.abs(audio_data))),
        rms_energy=float(np.sqrt(np.mean(audio_data ** 2))),
    )


@router.post("/spectrogram", response_model=SpectrogramResponse)
async def generate_spectrogram(
    audio_file: UploadFile = File(...),
    mode: str = "power",
):
    """
    Generate a spectrogram image from an uploaded audio file (WAV, MP3, MP4, FLAC, OGG, WEBM).

    Modes: "stft", "mel", "power"
    Returns base64-encoded PNG.
    """
    try:
        from core.audio_io import load_audio_bytes
        audio_bytes = await audio_file.read()
        filename = getattr(audio_file, "filename", None) or "audio"
        audio_data, sr = load_audio_bytes(audio_bytes, filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid audio file: {e}")

    try:
        from core.api import generate_spectrogram as gen_spec
        freqs, times, sxx = gen_spec(audio_data, sr, mode=mode)

        # Render to PNG using matplotlib
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(10, 4))
        fig.patch.set_facecolor("#1e1e2e")
        ax.set_facecolor("#1e1e2e")

        # Limit to 8kHz
        freq_mask = freqs <= 8000
        mesh = ax.pcolormesh(
            times, freqs[freq_mask], sxx[freq_mask, :],
            shading="gouraud", cmap="magma",
        )
        ax.set_ylabel("Frequency (Hz)", color="#cdd6f4")
        ax.set_xlabel("Time (s)", color="#cdd6f4")
        ax.tick_params(colors="#a6adc8")

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", facecolor="#1e1e2e")
        plt.close(fig)
        buf.seek(0)
        image_b64 = base64.b64encode(buf.read()).decode("utf-8")

    except Exception as e:
        logger.error("Spectrogram generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    return SpectrogramResponse(
        image_base64=image_b64,
        duration_seconds=len(audio_data) / sr,
        sample_rate=sr,
    )
