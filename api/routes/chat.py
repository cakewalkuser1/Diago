"""
Chat API route — DiagBot assistant.
Prefers Ollama (hosted by backend). Falls back to in-process model when Ollama is unavailable (local dev).
"""

import json
import logging
import urllib.error
import urllib.request

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
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
    photo_urls: list[str] = Field(default_factory=list)  # URLs of attached photos (for multimodal LLMs)


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    context: ChatContext | None = None


class ChatResponse(BaseModel):
    content: str
    error: str | None = None
    sources: list[str] = Field(default_factory=list, description="Reference titles used (ASE-aligned)")


# ---------------------------------------------------------------------------
# Ollama (hosted by backend)
# ---------------------------------------------------------------------------

def _build_system_prompt(ctx: ChatContext | None, rag_suffix: str = "") -> str:
    parts = [
        "You are DiagBot: the user's diagnostic buddy and professional mentor. "
        "You're in the car with them—friendly, supportive, and on their side—while sharing ASE-level expertise. "
        "Use 'we' when it fits (e.g. 'we can check...', 'let's rule out...'). Be concise but warm. "
        "Explain like a skilled mentor: clear, practical, and encouraging. "
        "If the user has provided context below, use it to tailor your answers."
    ]
    if ctx and (ctx.symptoms or ctx.vehicle or ctx.trouble_codes or ctx.diagnosis_summary or ctx.photo_urls):
        parts.append("\n\nCurrent context:")
        if ctx.vehicle:
            parts.append(f"\n- Vehicle: {ctx.vehicle}")
        if ctx.symptoms:
            parts.append(f"\n- Symptoms: {ctx.symptoms}")
        if ctx.trouble_codes:
            parts.append(f"\n- Trouble codes: {', '.join(ctx.trouble_codes)}")
        if ctx.diagnosis_summary:
            parts.append(f"\n- Diagnosis: {ctx.diagnosis_summary}")
        if ctx.photo_urls:
            parts.append(f"\n- User attached {len(ctx.photo_urls)} photo(s). Use them if the model supports vision.")
    if rag_suffix:
        parts.append(rag_suffix)
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


def _stream_ollama(messages: list[dict], system_prompt: str):
    """Stream Ollama response as SSE events. Yields (token, done) tuples."""
    settings = get_settings().llm
    url = f"{settings.ollama_url.rstrip('/')}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": [{"role": "system", "content": system_prompt}, *messages],
        "stream": True,
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
            buffer = ""
            for chunk in iter(lambda: resp.read(4096), b""):
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        token = obj.get("message", {}).get("content", "") or obj.get("response", "")
                        done = obj.get("done", False)
                        if token:
                            yield token, done
                        if done:
                            return
                    except json.JSONDecodeError:
                        continue
    except Exception as e:
        logger.debug("Ollama stream not used: %s", e)
        yield ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

def _prepare_chat(request: ChatRequest) -> tuple[list[dict], str, list[str]]:
    """Shared prep: messages, system_prompt, sources. Used by both stream and non-stream."""
    if not request.messages:
        raise HTTPException(status_code=400, detail="messages required")
    messages = []
    for m in request.messages:
        role = m.role if m.role in ("user", "assistant", "system") else "user"
        if role == "system":
            continue
        messages.append({"role": role, "content": (m.content or "").strip()})
    if not messages:
        raise HTTPException(status_code=400, detail="at least one user or assistant message required")

    last_user = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
    ctx_dict = None
    if request.context:
        ctx_dict = {
            "symptoms": request.context.symptoms or "",
            "vehicle": request.context.vehicle or "",
            "trouble_codes": " ".join(request.context.trouble_codes or []),
            "diagnosis_summary": request.context.diagnosis_summary or "",
        }
    try:
        from core.rag_diagnostic import retrieve, build_rag_prompt
        chunks = retrieve(last_user, ctx_dict, k=5)
        rag_suffix = build_rag_prompt(chunks, last_user, ctx_dict)
        sources = [c.title for c in chunks]
    except Exception as e:
        logger.debug("RAG retrieve skipped: %s", e)
        rag_suffix = ""
        sources = []
    system_prompt = _build_system_prompt(request.context, rag_suffix)
    return messages, system_prompt, sources


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """
    Stream DiagBot response token-by-token via SSE.
    Only works when Ollama is available. Frontend should fall back to POST / if this fails.
    """
    messages, system_prompt, sources = _prepare_chat(request)

    if not _ollama_reachable():
        raise HTTPException(
            status_code=503,
            detail="Streaming requires Ollama. Use POST / for non-streaming.",
        )

    def generate():
        try:
            for token, done in _stream_ollama(messages, system_prompt):
                if token:
                    yield f"data: {json.dumps({'token': token})}\n\n"
                if done:
                    yield f"data: {json.dumps({'sources': sources, 'done': True})}\n\n"
                    return
            yield f"data: {json.dumps({'sources': sources, 'done': True})}\n\n"
        except Exception as e:
            logger.exception("Stream error: %s", e)
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send messages to DiagBot. Backend proxies to Ollama (hosted by Diago).
    RAG augments with ASE-aligned reference material when available.
    """
    messages, system_prompt, sources = _prepare_chat(request)

    # 1) Try Ollama first (when hosted)
    if _ollama_reachable():
        content = _call_ollama(messages, system_prompt)
        if content:
            return ChatResponse(content=content, sources=sources)

    # 2) Fall back to in-process model (local dev, no Ollama/Docker)
    try:
        from api.inprocess_llm import chat_completion
        content = chat_completion(messages, system_prompt)
        err_prefixes = ("DiagBot needs", "Chat error:")
        if content and not any(content.startswith(p) for p in err_prefixes):
            return ChatResponse(content=content, sources=sources)
    except Exception as e:
        logger.debug("In-process chat skipped: %s", e)

    return ChatResponse(
        content="Chat service temporarily unavailable. Install Ollama (ollama.com) or run: pip install llama-cpp-python",
        error="no_backend",
        sources=[],
    )
