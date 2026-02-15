"""
In-process chat model — no Ollama or external process.
Downloads a small GGUF model on first use and runs inference with llama-cpp-python.
User runs nothing externally; DiagBot just works.
"""

import logging
import os
from pathlib import Path

from core.config import get_settings

logger = logging.getLogger(__name__)

# Default: TinyLlama 1.1B Chat Q4_K_M (~637MB). Hugging Face CDN.
DEFAULT_MODEL_URL = (
    "https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/"
    "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
)
MODEL_FILENAME = "diago_chat.gguf"

_llama_instance = None


def _model_path() -> Path:
    settings = get_settings()
    models_dir = Path(settings.user_data_dir) / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    return models_dir / MODEL_FILENAME


def _download_model() -> bool:
    """Download default GGUF to user data dir. Return True on success."""
    path = _model_path()
    if path.exists():
        return True
    url = os.environ.get("DIAGO_CHAT_MODEL_URL", DEFAULT_MODEL_URL)
    logger.info("Downloading chat model (one-time, ~600MB)...")
    try:
        import httpx
        with httpx.stream("GET", url, follow_redirects=True, timeout=600.0) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=65536):
                    f.write(chunk)
        if path.exists() and path.stat().st_size > 100_000:
            logger.info("Chat model ready at %s", path)
            return True
    except Exception as e:
        logger.warning("Download failed: %s", e)
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass
    return False


def _get_llama():
    """Lazy-load Llama (load on first chat). Return instance or None."""
    global _llama_instance
    if _llama_instance is not None:
        return _llama_instance
    try:
        from llama_cpp import Llama
    except ImportError:
        logger.warning("llama-cpp-python not installed; in-process chat disabled")
        return None
    path = _model_path()
    if not path.exists() and not _download_model():
        return None
    try:
        # n_ctx = 4096 for conversation history; small for memory
        _llama_instance = Llama(
            model_path=str(path),
            n_ctx=4096,
            n_threads=min(4, (os.cpu_count() or 2)),
            verbose=False,
        )
        return _llama_instance
    except Exception as e:
        logger.warning("Could not load chat model: %s", e)
        return None


def chat_completion(messages: list[dict], system_prompt: str, max_tokens: int = 512) -> str:
    """
    Run chat with in-process model. messages = [{"role":"user","content":"..."}, ...].
    Returns assistant reply or error string.
    """
    llm = _get_llama()
    if llm is None:
        return (
            "DiagBot needs the chat model. Install: pip install llama-cpp-python "
            "(see https://github.com/abetlen/llama-cpp-python). "
            "Then try again; the model will download automatically."
        )
    full = [{"role": "system", "content": system_prompt}]
    for m in messages:
        role = m.get("role", "user")
        if role == "system":
            continue
        full.append({"role": role, "content": (m.get("content") or "").strip()})
    try:
        out = llm.create_chat_completion(
            messages=full,
            max_tokens=max_tokens,
            temperature=0.5,
        )
        choice = (out.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        return (msg.get("content") or "").strip()
    except Exception as e:
        logger.exception("In-process chat failed")
        return f"Chat error: {e!s}"
