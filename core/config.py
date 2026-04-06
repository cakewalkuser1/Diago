"""
Centralized Configuration for Diago
Uses pydantic-settings to load from .env files, environment variables,
or fallback defaults. Single source of truth for all configurable values.

Priority (highest to lowest):
1. Environment variables
2. .env file in project root
3. Default values defined here
"""

import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_project_root() -> Path:
    """Return the project root directory (where main.py lives)."""
    # If running as a script, use the directory of the entry point
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _get_user_data_dir() -> Path:
    """
    Return the user-scoped data directory for Diago.
    - Windows: %APPDATA%/Diago
    - macOS:   ~/Library/Application Support/Diago
    - Linux:   ~/.local/share/diago
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "Diago"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Diago"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        return base / "diago"


# ---------------------------------------------------------------------------
# Settings classes
# ---------------------------------------------------------------------------

class AudioSettings(BaseSettings):
    """Audio recording and processing configuration."""
    model_config = SettingsConfigDict(env_prefix="DIAGO_AUDIO_")

    sample_rate: int = 44100
    channels: int = 1
    dtype: str = "float32"
    block_size: int = 1024
    bandpass_low_hz: float = 20.0
    bandpass_high_hz: float = 8000.0


class LLMSettings(BaseSettings):
    """LLM reasoning module configuration."""
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    llm_enabled: bool = Field(default=False, alias="LLM_ENABLED")
    llm_provider: Optional[str] = Field(default=None, alias="LLM_PROVIDER")

    # OpenAI
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")

    # Anthropic
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-4-20250514", alias="ANTHROPIC_MODEL")

    # Ollama (DiagBot chat: hosted by backend, users do not run locally)
    # OLLAMA_URL: point to your Ollama service (e.g. http://ollama:11434 in Docker)
    ollama_model: str = Field(default="llama3.1", alias="OLLAMA_MODEL")
    ollama_url: str = Field(default="http://localhost:11434", alias="OLLAMA_URL")
    ollama_auto_start: bool = Field(default=False, alias="OLLAMA_AUTO_START")


class AgentSettings(BaseSettings):
    """Mechanic Agent configuration."""
    model_config = SettingsConfigDict(env_prefix="", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    agent_enabled: bool = Field(default=False, alias="AGENT_ENABLED")
    agent_llm_provider: Optional[str] = Field(default=None, alias="MECHANIC_LLM_PROVIDER")

    # Provider-specific overrides for the agent
    mechanic_openai_model: str = Field(default="gpt-4o", alias="MECHANIC_OPENAI_MODEL")
    mechanic_anthropic_model: str = Field(
        default="claude-sonnet-4-20250514", alias="MECHANIC_ANTHROPIC_MODEL"
    )
    mechanic_ollama_model: str = Field(default="llama3.1", alias="MECHANIC_OLLAMA_MODEL")
    mechanic_ollama_url: str = Field(
        default="http://localhost:11434", alias="MECHANIC_OLLAMA_URL"
    )


class SearchSettings(BaseSettings):
    """Tavily web search configuration."""
    model_config = SettingsConfigDict(env_prefix="")

    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")


class DatabaseSettings(BaseSettings):
    """Database configuration."""
    model_config = SettingsConfigDict(env_prefix="DIAGO_DB_")

    path: str = ""  # Empty = auto (user data dir)
    # Optional path to OBD2 codes JSON; if set, used to seed trouble_code_definitions instead of bundled database/obd2_codes.json
    obd2_codes_path: str = ""


class AppSettings(BaseSettings):
    """
    Top-level application settings.
    Aggregates all sub-settings into one object.
    """
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application metadata
    app_name: str = "Diago"
    app_version: str = "0.1.0"
    debug: bool = Field(default=False, alias="DIAGO_DEBUG")
    # Comma-separated origins for CORS (e.g. "https://app.example.com"). Empty or not set = allow all (dev).
    cors_origins: str = Field(default="", alias="CORS_ORIGINS")

    # Sub-configurations
    audio: AudioSettings = Field(default_factory=AudioSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    search: SearchSettings = Field(default_factory=SearchSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)

    # Supabase
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_anon_key: str = Field(default="", alias="SUPABASE_ANON_KEY")
    supabase_jwt_secret: str = Field(default="", alias="SUPABASE_JWT_SECRET")
    # Backend: use the "Secret" key (sb_secret_...) from Dashboard → Settings → API. Accept either env name.
    supabase_service_role_key: str = Field(
        default="",
        validation_alias=AliasChoices("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SECRET_KEY"),
    )

    # Stripe
    stripe_secret_key: str = Field(default="", alias="STRIPE_SECRET_KEY")
    stripe_publishable_key: str = Field(default="", alias="STRIPE_PUBLISHABLE_KEY")
    stripe_webhook_secret: str = Field(default="", alias="STRIPE_WEBHOOK_SECRET")
    stripe_diy_price_id: str = Field(default="", alias="DIAGO_STRIPE_DIY_PRICE_ID")
    stripe_pro_mechanic_price_id: str = Field(default="", alias="DIAGO_STRIPE_PRO_MECHANIC_PRICE_ID")
    stripe_shop_price_id: str = Field(default="", alias="DIAGO_STRIPE_SHOP_PRICE_ID")
    stripe_part_price_cents: int = Field(default=4999, alias="DIAGO_STRIPE_PART_PRICE_CENTS")  # $49.99 default

    # External APIs (optional)
    car_api_key: str = Field(default="", alias="CAR_API_KEY")  # Car API (carapi.app) for OBD code fallback

    # Repair guides (cloud PostgreSQL); empty = no repair guide DB
    repair_guides_db_url: str = Field(default="", alias="REPAIR_GUIDES_DB_URL")

    # Developer bypass: skip diagnosis rate limit (local dev only; do not enable in production)
    disable_diagnosis_rate_limit: bool = Field(default=False, alias="DIAGO_DISABLE_RATE_LIMIT")

    # Web Push (optional): VAPID private key for mechanic job notifications
    vapid_private_key: str = Field(default="", alias="VAPID_PRIVATE_KEY")

    @property
    def project_root(self) -> Path:
        """Return the project root directory."""
        return _get_project_root()

    @property
    def user_data_dir(self) -> Path:
        """Return the user-scoped data directory, creating it if needed."""
        data_dir = _get_user_data_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    @property
    def db_path(self) -> str:
        """
        Return the database file path.
        Uses configured path if set, otherwise user data directory.
        """
        if self.database.path:
            return self.database.path
        return str(self.user_data_dir / "auto_audio.db")

    @property
    def obd2_codes_path(self) -> Optional[str]:
        """Path to OBD2 codes JSON for seeding; None = use bundled database/obd2_codes.json."""
        p = (self.database.obd2_codes_path or "").strip()
        return p if p else None


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    """
    Get the cached application settings singleton.
    Loads from .env file and environment variables on first call.
    """
    return AppSettings()


def reset_settings() -> None:
    """Clear the settings cache (useful for testing)."""
    get_settings.cache_clear()
