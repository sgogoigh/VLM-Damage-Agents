"""HTTP API tests via FastAPI TestClient (mock mode)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:   # triggers lifespan (builds the service)
        yield c


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "healthy"
    assert "config" in body


def test_providers(client):
    r = client.get("/api/providers")
    assert r.status_code == 200
    body = r.json()
    assert body["default_provider"] in {"gemini", "claude"}
    names = {p["provider"] for p in body["providers"]}
    assert names == {"gemini", "claude"}


def test_verify_validation_error(client):
    # missing user_claim / empty image list
    r = client.post("/api/verify", json={"user_id": "u", "claim_object": "car",
                                          "user_claim": "x", "image_paths": []})
    assert r.status_code == 422


def test_verify_bad_claim_object(client):
    r = client.post("/api/verify", json={"user_id": "u", "claim_object": "boat",
                                         "user_claim": "x", "image_paths": ["a.jpg"]})
    assert r.status_code == 422   # enum rejects unknown object


def test_verify_missing_image_404(client):
    r = client.post("/api/verify", json={
        "user_id": "u", "claim_object": "car", "user_claim": "dent on door",
        "image_paths": ["images/test/case_999/img_1.jpg"], "provider": "gemini",
    })
    assert r.status_code == 404


def test_verify_success_mock(client, settings):
    if not settings.dataset_dir.exists():
        return
    r = client.post("/api/verify", json={
        "user_id": "user_001", "claim_object": "car",
        "user_claim": "The rear bumper has a dent.",
        "image_paths": ["images/sample/case_001/img_1.jpg"], "provider": "gemini",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "gemini"
    pred = body["prediction"]
    assert pred["claim_status"] in {"supported", "contradicted", "not_enough_information"}
    assert isinstance(pred["risk_flags"], list)
    assert isinstance(pred["image_paths"], list)


def test_samples_endpoint(client, settings):
    if not settings.dataset_dir.exists():
        return
    r = client.get("/api/samples?split=sample")
    assert r.status_code == 200
    body = r.json()
    assert body["split"] == "sample"
    assert body["count"] > 0
    case = body["cases"][0]
    assert case["labeled"] is True
    assert case["expected"] is not None
    assert isinstance(case["image_paths"], list) and case["image_paths"]
    assert case["case_id"].startswith("sample/")


def test_samples_split_validation(client):
    r = client.get("/api/samples?split=bogus")
    assert r.status_code == 422


def test_samples_test_split_unlabeled(client, settings):
    if not settings.dataset_dir.exists():
        return
    r = client.get("/api/samples?split=test")
    assert r.status_code == 200
    body = r.json()
    assert all(c["labeled"] is False for c in body["cases"])


def test_static_image_served(client, settings):
    if not settings.dataset_dir.exists():
        return
    r = client.get("/dataset/images/sample/case_001/img_1.jpg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/")


def test_batch_isolates_failures(client, settings):
    if not settings.dataset_dir.exists():
        return
    r = client.post("/api/batch", json={"claims": [
        {"user_id": "user_001", "claim_object": "car", "user_claim": "rear bumper dent",
         "image_paths": ["images/sample/case_001/img_1.jpg"]},
        {"user_id": "u", "claim_object": "car", "user_claim": "dent",
         "image_paths": ["images/test/case_999/img_1.jpg"]},
    ]})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["succeeded"] == 1
    assert body["failed"] == 1
    assert body["results"][1]["ok"] is False
