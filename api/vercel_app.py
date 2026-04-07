"""
Vercel serverless entry point.
Wraps the FastAPI app for Vercel's Python runtime.
"""
import sys
import os

# Add repo root to path so imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.main import app  # noqa: E402 — must come after sys.path tweak

# Vercel expects a callable named `app`
__all__ = ["app"]
