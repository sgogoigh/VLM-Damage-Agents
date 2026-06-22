"""
Central configuration for the standalone Orchestrate claim-verifier backend.

Design:
- All secrets come from the environment only (AGENTS.md §6.2). A local
  ``backend/.env`` is loaded if present so keys are never hardcoded.
- Settings are a single, cached, immutable object (`get_settings()`), suitable
  for FastAPI dependency injection and for tests (override env, clear the cache).
- ``mock`` is derived per-provider: a provider with no API key (or a global
  ``LLM_MOCK=1``) runs deterministic offline stubs, so the whole service runs
  end-to-end with no network and no key.

This package is fully standalone: nothing here imports the sibling ``code/``
package or assumes a particular current working directory.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Anchor paths off this file, never off the current working directory, so the
# service behaves identically whether launched from backend/ or the repo root.
# ---------------------------------------------------------------------------
APP_DIR = Path(__file__).resolve().parent              # backend/app
BACKEND_ROOT = APP_DIR.parent                          # backend/
REPO_ROOT = BACKEND_ROOT.parent                        # repo root
ENV_PATH = BACKEND_ROOT / ".env"

# Load backend/.env first (highest priority for this service), then fall back to
# any .env discoverable from the cwd. ``override=False`` means a real exported
# environment variable always wins over the file.
load_dotenv(ENV_PATH, override=False)
load_dotenv(override=False)


_TRUTHY = {"1", "true", "yes", "on"}


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in _TRUTHY


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_PATH),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # -- provider selection -------------------------------------------------
    default_provider: str = Field(default="gemini")

    # -- Google Gemini ------------------------------------------------------
    gemini_api_key: str = Field(default="")
    # Gemini 3.5 Flash: current vision-capable flash model that supports
    # thinking_level (verified live against this key).
    gemini_model: str = Field(default="gemini-3.5-flash")
    # Gemini 3.x: minimal|low|medium|high (replaces thinking_budget). Empty => omit.
    gemini_thinking_level: str = Field(default="low")
    # Free-tier flash is ~5 RPM; client-side throttle paces calls to stay under.
    gemini_rpm: int = Field(default=5)

    # -- Anthropic Claude (optional alternative VLM) ------------------------
    anthropic_api_key: str = Field(default="")
    claude_model: str = Field(default="claude-opus-4-8")
    claude_max_tokens: int = Field(default=2048)

    # -- global mock switch -------------------------------------------------
    # Forces every provider into deterministic offline mode regardless of keys.
    llm_mock: bool = Field(default=False)

    # -- resilience / rate-limit knobs --------------------------------------
    max_retries: int = Field(default=5)
    retry_base_delay_s: float = Field(default=2.0)
    request_timeout_s: int = Field(default=60)

    # -- filesystem ---------------------------------------------------------
    # Where the dataset (images + reference CSVs) lives. Defaults to the
    # repo-level ``dataset/`` dir; override with DATASET_DIR for other layouts.
    dataset_dir: Path = Field(default=REPO_ROOT / "dataset")
    cache_dir: Path = Field(default=BACKEND_ROOT / ".cache")

    # -- HTTP / API ---------------------------------------------------------
    api_prefix: str = Field(default="/api")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    log_level: str = Field(default="INFO")

    @field_validator("default_provider", mode="before")
    @classmethod
    def _norm_provider(cls, v: str) -> str:
        return (v or "gemini").strip().lower()

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator("gemini_api_key", "anthropic_api_key", mode="before")
    @classmethod
    def _strip_key(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v

    # -- derived paths ------------------------------------------------------
    @property
    def user_history_csv(self) -> Path:
        return self.dataset_dir / "user_history.csv"

    @property
    def evidence_requirements_csv(self) -> Path:
        return self.dataset_dir / "evidence_requirements.csv"

    @property
    def sample_claims_csv(self) -> Path:
        return self.dataset_dir / "sample_claims.csv"

    @property
    def claims_csv(self) -> Path:
        return self.dataset_dir / "claims.csv"

    @property
    def images_root(self) -> Path:
        # CSV paths look like "images/test/case_001/img_1.jpg" and resolve
        # against the dataset dir.
        return self.dataset_dir

    # -- derived provider readiness ----------------------------------------
    @property
    def gemini_mock(self) -> bool:
        return self.llm_mock or not self.gemini_api_key

    @property
    def claude_mock(self) -> bool:
        return self.llm_mock or not self.anthropic_api_key

    def provider_mock(self, provider: str) -> bool:
        return self.claude_mock if provider == "claude" else self.gemini_mock

    def model_for(self, provider: str) -> str:
        return self.claude_model if provider == "claude" else self.gemini_model

    def public_summary(self) -> dict[str, object]:
        """Secret-free snapshot for /health and logs."""
        return {
            "default_provider": self.default_provider,
            "gemini": {
                "model": self.gemini_model,
                "mock": self.gemini_mock,
                "api_key_present": bool(self.gemini_api_key),
            },
            "claude": {
                "model": self.claude_model,
                "mock": self.claude_mock,
                "api_key_present": bool(self.anthropic_api_key),
            },
            "dataset_dir": str(self.dataset_dir),
            "dataset_present": self.dataset_dir.exists(),
            "max_retries": self.max_retries,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings singleton. Clear with ``get_settings.cache_clear()`` in tests."""
    # Allow LLM_MOCK to be supplied as a truthy string in the environment.
    if "LLM_MOCK" in os.environ:
        os.environ["LLM_MOCK"] = "true" if _is_truthy(os.environ["LLM_MOCK"]) else "false"
    return Settings()


# Convenience module-level handle (most call sites should prefer get_settings()).
settings = get_settings()
