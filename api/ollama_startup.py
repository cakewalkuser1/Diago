"""
Ensure Ollama is running so DiagBot works (optional, for single-host deployments).

When OLLAMA_AUTO_START is true and Ollama isn't reachable at OLLAMA_URL, we start
`ollama serve` in the background. In centralized deployments, run Ollama as a
separate service and set OLLAMA_AUTO_START=false; OLLAMA_URL should point to
your Ollama instance (e.g. http://ollama:11434 in Docker).
"""

import asyncio
import logging
import subprocess
import sys
import urllib.request

from core.config import get_settings

logger = logging.getLogger(__name__)


def _ollama_reachable() -> bool:
    """Return True if Ollama is up."""
    settings = get_settings().llm
    url = f"{settings.ollama_url.rstrip('/')}/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as _:
            return True
    except Exception:
        return False


def _start_ollama_serve() -> bool:
    """
    Start `ollama serve` in the background (detached). Return True if we launched it.
    """
    try:
        args = ["ollama", "serve"]
        if sys.platform == "win32":
            # Detach so the process keeps running; no console window
            subprocess.Popen(
                args,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW
                    | subprocess.DETACHED_PROCESS
                    | subprocess.CREATE_NEW_PROCESS_GROUP
                ),
            )
        else:
            subprocess.Popen(
                args,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
            )
        logger.info("Started Ollama in the background (ollama serve)")
        return True
    except FileNotFoundError:
        logger.warning(
            "Ollama not found in PATH. Install from https://ollama.com so DiagBot can run."
        )
        return False
    except Exception as e:
        logger.warning("Could not start Ollama: %s", e)
        return False


async def ensure_ollama_running() -> None:
    """
    If Ollama isn't reachable and auto-start is enabled, start it and wait briefly.
    Run this in the background at API startup so DiagBot works without user setup.
    """
    settings = get_settings().llm
    if not settings.ollama_auto_start:
        return
    if _ollama_reachable():
        logger.debug("Ollama already running")
        return
    logger.info("Ollama not reachable; attempting to start it for DiagBot...")
    started = _start_ollama_serve()
    if started:
        await asyncio.sleep(4)
        if _ollama_reachable():
            logger.info("Ollama is now running")
        else:
            logger.warning("Ollama may still be starting. DiagBot will work once it's up.")
