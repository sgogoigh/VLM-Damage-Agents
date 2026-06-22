"""Shared test fixtures.

The default suite runs entirely in deterministic MOCK mode — no network, no key.
``LLM_MOCK=1`` is forced for the session *before* the app package is imported,
so ``get_settings()`` and the FastAPI app both start mocked. The gated live test
(``test_live_gemini.py``) builds its own un-mocked ``Settings`` explicitly.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Make the backend root importable (so `import app...` works from anywhere) and
# force mock mode BEFORE anything from `app` is imported.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
os.environ["LLM_MOCK"] = "1"

import pytest  # noqa: E402

from app.config import Settings, get_settings  # noqa: E402
from app.service import ClaimVerifierService  # noqa: E402

# Reset any cached settings captured at import time so LLM_MOCK takes effect.
get_settings.cache_clear()


@pytest.fixture
def settings() -> Settings:
    return get_settings()


@pytest.fixture
def service(settings: Settings) -> ClaimVerifierService:
    return ClaimVerifierService(settings)


@pytest.fixture
def sample_image_rel(settings: Settings) -> str:
    """A real sample image path that resolves under the dataset root."""
    return "images/sample/case_001/img_1.jpg"


@pytest.fixture
def dataset_available(settings: Settings) -> bool:
    return settings.dataset_dir.exists()
