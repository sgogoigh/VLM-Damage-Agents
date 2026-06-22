"""
Application service layer — the seam between the HTTP API and the core pipeline.

``ClaimVerifierService`` owns the expensive, reusable state so it is loaded once
and shared across requests:
  - reference data (user history, evidence requirements) read at construction;
  - one VLM client per provider (lazily created, then cached);
  - a single content-addressed analysis cache.

This is what makes the service efficient and standalone: the old wrapper rebuilt
the client and re-read both CSVs on every single request.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.config import Settings, get_settings
from app.core.cache import AnalysisCache
from app.core.contract import CLAIM_OBJECTS, OUTPUT_COLUMNS, ClaimRecord, PredictionRow
from app.core.data_io import (
    image_exists,
    read_claims,
    read_evidence_requirements,
    read_sample_with_labels,
    read_user_history,
)
from app.core.llm import PROVIDERS, make_client
from app.core.llm.base import BaseLLMClient
from app.core.pipeline import run_pipeline

logger = logging.getLogger("orchestrate.service")


class ImageNotFoundError(FileNotFoundError):
    """One or more requested image paths do not resolve under the dataset root."""

    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__("Image(s) not found: " + ", ".join(missing))


class ClaimVerifierService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._cache = AnalysisCache(self.settings.cache_dir)
        self._clients: dict[str, BaseLLMClient] = {}
        self._history: dict[str, dict[str, str]] = {}
        self._requirements: list[dict] = []
        self.reload_reference_data()

    # -- lifecycle ----------------------------------------------------------
    def reload_reference_data(self) -> None:
        """(Re)load user history + evidence requirements from the dataset."""
        self._history = read_user_history(self.settings.user_history_csv)
        self._requirements = read_evidence_requirements(self.settings.evidence_requirements_csv)
        logger.info(
            "Loaded reference data: %d users, %d requirement rules (dataset=%s)",
            len(self._history), len(self._requirements), self.settings.dataset_dir,
        )

    def get_client(self, provider: str | None = None) -> BaseLLMClient:
        name = (provider or self.settings.default_provider or "gemini").strip().lower()
        if name not in PROVIDERS:
            raise ValueError(f"Unknown provider {provider!r}; expected one of {PROVIDERS}.")
        if name not in self._clients:
            self._clients[name] = make_client(name, settings=self.settings)
            logger.info("Initialised %s client (mock=%s)", name, self._clients[name].mock)
        return self._clients[name]

    # -- core operation -----------------------------------------------------
    def verify(
        self,
        *,
        user_id: str,
        claim_object: str,
        user_claim: str,
        image_paths: list[str],
        provider: str | None = None,
        strict_images: bool = True,
    ) -> PredictionRow:
        """Run the full verification pipeline for a single claim.

        With ``strict_images`` (the API default), raises ``ImageNotFoundError``
        if any image path is missing. Batch/CSV runs pass ``strict_images=False``
        so a missing file yields a graceful "not_enough_information" row instead
        of aborting the whole run (the pipeline marks the image as missing).
        Raises ``ValueError`` for an empty image list or an unknown provider.
        """
        normalized = [p.strip() for p in (image_paths or []) if p and p.strip()]
        if not normalized:
            raise ValueError("At least one image path is required.")

        if strict_images:
            missing = [p for p in normalized if not image_exists(p, self.settings)]
            if missing:
                raise ImageNotFoundError(missing)

        claim_obj = (claim_object or "").strip().lower()
        if claim_obj not in CLAIM_OBJECTS:
            logger.warning("claim_object %r is outside the known set %s; "
                           "object_part vocabulary will be limited.", claim_object, CLAIM_OBJECTS)

        client = self.get_client(provider)
        record = ClaimRecord(
            user_id=user_id.strip(),
            image_paths=";".join(normalized),
            user_claim=user_claim.strip(),
            claim_object=claim_obj,
        )
        prediction = run_pipeline(
            record,
            history=self._history,
            requirements=self._requirements,
            client=client,
            cache=self._cache,
        )
        logger.info("verify user=%s provider=%s -> %s",
                    record.user_id, client.name, prediction.claim_status)
        return prediction

    def verify_to_api_dict(self, **kwargs: Any) -> dict[str, Any]:
        return self.verify(**kwargs).to_api_dict()

    # -- introspection ------------------------------------------------------
    def provider_status(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for name in PROVIDERS:
            mock = self.settings.provider_mock(name)
            out.append({
                "provider": name,
                "model": self.settings.model_for(name),
                "mock": mock,
                "operational": not mock,
                "is_default": name == self.settings.default_provider,
            })
        return out

    def list_cases(self, split: str = "sample") -> list[dict[str, Any]]:
        """List demo cases from the dataset for the UI's case browser.

        ``sample`` rows carry ground-truth labels (expected output); ``test``
        rows are input-only. ``all`` returns both.
        """
        split = (split or "sample").strip().lower()
        cases: list[dict[str, Any]] = []

        if split in ("sample", "all"):
            for i, row in enumerate(read_sample_with_labels(self.settings.sample_claims_csv)):
                paths = [p.strip() for p in (row.get("image_paths") or "").split(";") if p.strip()]
                expected = {c: row[c] for c in OUTPUT_COLUMNS if c in row}
                cases.append({
                    "case_id": self._case_id(paths, "sample", i),
                    "split": "sample",
                    "user_id": (row.get("user_id") or "").strip(),
                    "claim_object": (row.get("claim_object") or "").strip().lower(),
                    "user_claim": (row.get("user_claim") or "").strip(),
                    "image_paths": paths,
                    "labeled": True,
                    "expected": expected,
                })

        if split in ("test", "all"):
            for i, rec in enumerate(read_claims(self.settings.claims_csv)):
                cases.append({
                    "case_id": self._case_id(rec.image_path_list, "test", i),
                    "split": "test",
                    "user_id": rec.user_id,
                    "claim_object": rec.claim_object,
                    "user_claim": rec.user_claim,
                    "image_paths": rec.image_path_list,
                    "labeled": False,
                    "expected": None,
                })
        return cases

    @staticmethod
    def _case_id(paths: list[str], split: str, index: int) -> str:
        if paths:
            parent = Path(paths[0]).parent.name
            if parent:
                return f"{split}/{parent}"
        return f"{split}/{index:03d}"

    def health(self) -> dict[str, Any]:
        return {
            "status": "healthy",
            "reference_data": {
                "users": len(self._history),
                "requirement_rules": len(self._requirements),
            },
            "config": self.settings.public_summary(),
        }
