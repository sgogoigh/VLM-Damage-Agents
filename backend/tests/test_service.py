"""Service layer: verify, validation, image strictness, introspection."""
from __future__ import annotations

import pytest

from app.service import ClaimVerifierService, ImageNotFoundError


def test_provider_status(service: ClaimVerifierService):
    statuses = {p["provider"]: p for p in service.provider_status()}
    assert set(statuses) == {"gemini", "claude"}
    assert statuses["gemini"]["mock"] is True          # no key in test env
    assert statuses["gemini"]["operational"] is False


def test_health_shape(service: ClaimVerifierService):
    h = service.health()
    assert h["status"] == "healthy"
    assert "reference_data" in h
    assert "gemini" in h["config"]
    # secret-free
    assert "api_key" not in str(h["config"]).lower() or "api_key_present" in str(h["config"])


def test_verify_empty_images_raises(service: ClaimVerifierService):
    with pytest.raises(ValueError):
        service.verify(user_id="u", claim_object="car", user_claim="c", image_paths=[])


def test_verify_missing_image_strict_raises(service: ClaimVerifierService):
    with pytest.raises(ImageNotFoundError):
        service.verify(user_id="u", claim_object="car", user_claim="dent on door",
                       image_paths=["images/test/case_999/img_1.jpg"])


def test_verify_missing_image_nonstrict_graceful(service: ClaimVerifierService):
    pred = service.verify(user_id="u", claim_object="car", user_claim="dent on door",
                          image_paths=["images/test/case_999/img_1.jpg"], strict_images=False)
    assert pred.claim_status == "not_enough_information"


def test_verify_unknown_provider_raises(service: ClaimVerifierService, dataset_available, sample_image_rel):
    if not dataset_available:
        return
    with pytest.raises(ValueError):
        service.verify(user_id="u", claim_object="car", user_claim="dent",
                       image_paths=[sample_image_rel], provider="midjourney")


def test_verify_real_sample_mock(service: ClaimVerifierService, dataset_available, sample_image_rel):
    if not dataset_available:
        return
    pred = service.verify(user_id="user_001", claim_object="car",
                          user_claim="The rear bumper has a dent.",
                          image_paths=[sample_image_rel])
    assert pred.claim_status in {"supported", "contradicted", "not_enough_information"}
    api = pred.to_api_dict()
    assert isinstance(api["risk_flags"], list)
    assert isinstance(api["image_paths"], list)


def test_clients_cached(service: ClaimVerifierService):
    c1 = service.get_client("gemini")
    c2 = service.get_client("gemini")
    assert c1 is c2   # cached, not rebuilt per call
