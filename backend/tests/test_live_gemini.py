"""Gated live smoke test against the real Gemini API.

Skipped unless RUN_LIVE=1 and a GEMINI_API_KEY is available. This actually spends
free-tier quota, so it is excluded from the default suite.

    RUN_LIVE=1 pytest -m live
"""
from __future__ import annotations

import os

import pytest

from app.config import Settings
from app.core.contract import CLAIM_STATUS
from app.service import ClaimVerifierService

pytestmark = pytest.mark.live


def _live_settings() -> Settings:
    # Explicitly un-mock; key is read from the environment / backend/.env.
    return Settings(llm_mock=False)


@pytest.mark.skipif(os.getenv("RUN_LIVE") != "1", reason="set RUN_LIVE=1 to run live API tests")
def test_live_gemini_verify_sample():
    settings = _live_settings()
    if not settings.gemini_api_key:
        pytest.skip("GEMINI_API_KEY not set")
    if not settings.dataset_dir.exists():
        pytest.skip("dataset not available")
    assert settings.gemini_mock is False  # genuinely live

    service = ClaimVerifierService(settings)
    pred = service.verify(
        user_id="user_001",
        claim_object="car",
        user_claim="The rear bumper has a dent. Photo attached.",
        image_paths=["images/sample/case_001/img_1.jpg"],
        provider="gemini",
    )
    # A real VLM run should yield a schema-valid, decisive-or-NEI result.
    assert pred.claim_status in CLAIM_STATUS
    api = pred.to_api_dict()
    assert api["claim_object"] == "car"
    assert isinstance(api["risk_flags"], list)
    print("\n[live gemini] ->", pred.claim_status, "| part:", pred.object_part,
          "| issue:", pred.issue_type, "| severity:", pred.severity)
