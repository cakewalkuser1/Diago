"""
Chat API route — DiagBot assistant.
Prefers Ollama (hosted by backend). Falls back to in-process model when Ollama is unavailable (local dev).
"""

import json
import logging
import urllib.error
import urllib.request

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from core.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant" | "system"
    content: str


class ChatContext(BaseModel):
    """Optional context so the assistant can tailor answers."""
    symptoms: str = ""
    vehicle: str = ""  # e.g. "2020 Honda Accord"
    trouble_codes: list[str] = Field(default_factory=list)
    diagnosis_summary: str = ""  # e.g. "Belt Drive / Friction, high confidence"


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    context: ChatContext | None = None


class ChatResponse(BaseModel):
    content: str
    error: str | None = None


# ---------------------------------------------------------------------------
# Ollama (hosted by backend)
# ---------------------------------------------------------------------------

def _build_system_prompt(ctx: ChatContext | None) -> str:
    parts = [
        "You are DiagBot, an ASE-style automotive diagnostic assistant. "
        "Answer concisely and helpfully about car symptoms, trouble codes, and repairs. "
        "If the user has provided context below, use it to tailor your answers."
    ]
    if ctx and (ctx.symptoms or ctx.vehicle or ctx.trouble_codes or ctx.diagnosis_summary):
        parts.append("\n\nCurrent context:")
        if ctx.vehicle:
            parts.append(f"\n- Vehicle: {ctx.vehicle}")
        if ctx.symptoms:
            parts.append(f"\n- Symptoms: {ctx.symptoms}")
        if ctx.trouble_codes:
            parts.append(f"\n- Trouble codes: {', '.join(ctx.trouble_codes)}")
        if ctx.diagnosis_summary:
            parts.append(f"\n- Diagnosis: {ctx.diagnosis_summary}")
    return "".join(parts)


def _ollama_reachable() -> bool:
    settings = get_settings().llm
    url = f"{settings.ollama_url.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=2) as _:
            return True
    except Exception:
        return False


def _call_ollama(messages: list[dict], system_prompt: str) -> str | None:
    """Return assistant content or None if Ollama unavailable."""
    settings = get_settings().llm
    url = f"{settings.ollama_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "stream": False,
        "options": {"temperature": 0.5, "num_predict": 1024},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            out = json.loads(resp.read().decode("utf-8"))
            return (out.get("message") or {}).get("content", "")
    except Exception as e:
        logger.debug("Ollama not used: %s", e)
        return None


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send messages to DiagBot. Backend proxies to Ollama (hosted by Diago).
    Optional context tailors answers.
    """
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages required")
    system_prompt = _build_system_prompt(request.context)
    messages = []
    for m in request.messages:
        role = m.role if m.role in ("user", "assistant", "system") else "user"
        if role == "system":
            continue
        messages.append({"role": role, "content": (m.content or "").strip()})
    if not messages:
        raise HTTPException(status_code=400, detail="at least one user or assistant message required")

    # 1) Try Ollama first (when hosted)
    if _ollama_reachable():
        content = _call_ollama(messages, system_prompt)
        if content:
            return ChatResponse(content=content)

    # 2) Fall back to in-process model (local dev, no Ollama/Docker)
    try:
        from api.inprocess_llm import chat_completion
        content = chat_completion(messages, system_prompt)
        err_prefixes = ("DiagBot needs", "Chat error:")
        if content and not any(content.startswith(p) for p in err_prefixes):
            return ChatResponse(content=content)
    except Exception as e:
        logger.debug("In-process chat skipped: %s", e)

    return ChatResponse(
        content="Chat service temporarily unavailable. Install Ollama (ollama.com) or run: pip install llama-cpp-python",
        error="no_backend",
    )
