"""
Central configuration for the Multi-Modal Evidence Review system.

All secrets are read from the environment only (AGENTS.md S6.2). A local
`.env` file is loaded if present so you never have to hardcode keys.

Provider: Google Gemini (free tier) via the `google-genai` SDK.
"""
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (resolved relative to the repo root, never hardcoded absolutes)
# ---------------------------------------------------------------------------
CODE_DIR = Path(__file__).resolve().parent
REPO_ROOT = CODE_DIR.parent
DATASET_DIR = REPO_ROOT / "dataset"

# ---------------------------------------------------------------------------
# .env loading (no hard dependency if python-dotenv is missing).
# Load `code/.env` explicitly so it works regardless of the current working
# directory, then fall back to the default cwd/parent search.
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(CODE_DIR / ".env")
    load_dotenv()  # also honor a .env in cwd/parents if present
except Exception:  # pragma: no cover - dotenv is optional
    pass

SAMPLE_CLAIMS_CSV = DATASET_DIR / "sample_claims.csv"
CLAIMS_CSV = DATASET_DIR / "claims.csv"
USER_HISTORY_CSV = DATASET_DIR / "user_history.csv"
EVIDENCE_REQUIREMENTS_CSV = DATASET_DIR / "evidence_requirements.csv"

# Image paths inside the CSVs look like "images/test/case_001/img_1.jpg" and
# are resolved relative to DATASET_DIR.
IMAGES_ROOT = DATASET_DIR

# Default output location (overridable via CLI / OUTPUT_CSV env var).
DEFAULT_OUTPUT_CSV = REPO_ROOT / "output.csv"

# On-disk cache for per-image VLM analysis (keyed by image content hash) so
# multi-image cases and re-runs do not re-bill the same image.
CACHE_DIR = CODE_DIR / ".cache"


# ---------------------------------------------------------------------------
# Model / provider configuration
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

# A vision-capable Gemini model on the free tier. Configurable so we can
# compare configs in the evaluation report (problem_statement.md "Evaluation").
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip()

# Gemini 3.x removed temperature/top_p/top_k and replaced thinking_budget with
# thinking_level (minimal|low|medium|high). low/minimal = deterministic + fast
# for structured JSON extraction. Empty string => omit thinking_config.
GEMINI_THINKING_LEVEL = os.getenv("GEMINI_THINKING_LEVEL", "low").strip()

# MOCK_MODE: when True, the pipeline runs end-to-end with deterministic stub
# analysis instead of calling the API. This is the default when no key is set
# OR when LLM_MOCK is truthy, so iteration-1 scaffolding never spends tokens.
_FORCE_MOCK = os.getenv("LLM_MOCK", "").strip().lower() in {"1", "true", "yes"}
MOCK_MODE = _FORCE_MOCK or not GEMINI_API_KEY


# ---------------------------------------------------------------------------
# Rate-limit / cost knobs (free-tier Gemini is RPM/RPD limited; see report)
# ---------------------------------------------------------------------------
MAX_CONCURRENCY = int(os.getenv("MAX_CONCURRENCY", "4"))
REQUEST_TIMEOUT_S = int(os.getenv("REQUEST_TIMEOUT_S", "60"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
RETRY_BASE_DELAY_S = float(os.getenv("RETRY_BASE_DELAY_S", "2.0"))

# Free-tier gemini-3.5-flash is limited to ~5 requests/minute. Client-side
# throttle spaces calls to stay under this; raise if you have a paid tier.
GEMINI_RPM = int(os.getenv("GEMINI_RPM", "5"))


def summary() -> str:
    """Human-readable config summary (no secrets)."""
    return (
        f"model={GEMINI_MODEL} mock_mode={MOCK_MODE} "
        f"api_key={'set' if GEMINI_API_KEY else 'MISSING'} "
        f"concurrency={MAX_CONCURRENCY} retries={MAX_RETRIES}"
    )
