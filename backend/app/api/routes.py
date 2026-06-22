"""API routes for claim verification.

Endpoints are ``async`` but the verification pipeline is blocking (network I/O to
the VLM), so it is offloaded to a worker thread with ``run_in_threadpool`` to
keep the event loop responsive under concurrent requests.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool

from app.schemas import (
    BatchItemResult,
    BatchVerifyRequest,
    BatchVerifyResponse,
    ClaimPrediction,
    ClaimVerifyRequest,
    ClaimVerifyResponse,
    HealthResponse,
    Provider,
    ProvidersResponse,
    SampleCase,
    SamplesResponse,
)
from app.service import ClaimVerifierService, ImageNotFoundError

logger = logging.getLogger("orchestrate.api")

router = APIRouter()


def get_service(request: Request) -> ClaimVerifierService:
    """Return the singleton service created during application startup."""
    service: ClaimVerifierService | None = getattr(request.app.state, "service", None)
    if service is None:  # pragma: no cover - lifespan always sets this
        raise HTTPException(status_code=503, detail="Service not initialised.")
    return service


@router.get("/health", response_model=HealthResponse)
async def health(service: ClaimVerifierService = Depends(get_service)) -> HealthResponse:
    return HealthResponse(**service.health())


@router.get("/providers", response_model=ProvidersResponse)
async def providers(service: ClaimVerifierService = Depends(get_service)) -> ProvidersResponse:
    return ProvidersResponse(
        default_provider=service.settings.default_provider,
        providers=service.provider_status(),
    )


@router.get("/samples", response_model=SamplesResponse)
async def samples(
    split: str = Query("sample", pattern="^(sample|test|all)$"),
    service: ClaimVerifierService = Depends(get_service),
) -> SamplesResponse:
    """Demo/test cases from the dataset, for the UI's case browser."""
    cases = service.list_cases(split)
    return SamplesResponse(
        split=split,
        count=len(cases),
        cases=[SampleCase(**c) for c in cases],
    )


@router.post("/verify", response_model=ClaimVerifyResponse)
async def verify_claim(
    request: ClaimVerifyRequest,
    service: ClaimVerifierService = Depends(get_service),
) -> ClaimVerifyResponse:
    provider = request.provider.value if request.provider else None
    try:
        prediction = await run_in_threadpool(
            service.verify_to_api_dict,
            user_id=request.user_id,
            claim_object=request.claim_object.value,
            user_claim=request.user_claim,
            image_paths=list(request.image_paths),
            provider=provider,
        )
    except ImageNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.exception("verify failed")
        raise HTTPException(status_code=502, detail=f"Verification failed: {exc}")

    resolved = service.get_client(provider).name
    return ClaimVerifyResponse(
        provider=Provider(resolved),
        prediction=ClaimPrediction(**prediction),
    )


@router.post("/batch", response_model=BatchVerifyResponse)
async def verify_batch(
    request: BatchVerifyRequest,
    service: ClaimVerifierService = Depends(get_service),
) -> BatchVerifyResponse:
    """Verify many claims in one call. Per-item failures are isolated."""
    batch_provider = request.provider.value if request.provider else None
    results: list[BatchItemResult] = []
    succeeded = 0

    for i, claim in enumerate(request.claims):
        provider = batch_provider or (claim.provider.value if claim.provider else None)
        try:
            prediction = await run_in_threadpool(
                service.verify_to_api_dict,
                user_id=claim.user_id,
                claim_object=claim.claim_object.value,
                user_claim=claim.user_claim,
                image_paths=list(claim.image_paths),
                provider=provider,
            )
            results.append(BatchItemResult(index=i, ok=True,
                                           prediction=ClaimPrediction(**prediction)))
            succeeded += 1
        except Exception as exc:  # noqa: BLE001 - isolate one bad row
            logger.warning("batch item %d failed: %s", i, exc)
            results.append(BatchItemResult(index=i, ok=False, error=str(exc)))

    resolved = service.get_client(batch_provider).name
    return BatchVerifyResponse(
        provider=Provider(resolved),
        total=len(request.claims),
        succeeded=succeeded,
        failed=len(request.claims) - succeeded,
        results=results,
    )
