"""Pydantic request/response models for the public API."""
from __future__ import annotations

from enum import Enum
from typing import Annotated, List, Optional

from pydantic import BaseModel, Field, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class Provider(str, Enum):
    gemini = "gemini"
    claude = "claude"


class ClaimObject(str, Enum):
    car = "car"
    laptop = "laptop"
    package = "package"


class ClaimVerifyRequest(BaseModel):
    user_id: NonEmptyStr = Field(..., examples=["user_001"])
    claim_object: ClaimObject = Field(..., examples=["car"])
    user_claim: NonEmptyStr = Field(
        ..., examples=["Customer: The rear bumper has a dent. I attached a photo."]
    )
    image_paths: List[NonEmptyStr] = Field(
        ..., min_length=1, examples=[["images/sample/case_001/img_1.jpg"]]
    )
    provider: Optional[Provider] = Field(
        default=None, description="VLM provider; defaults to the server's configured provider."
    )


class ClaimPrediction(BaseModel):
    user_id: str
    image_paths: List[str]
    user_claim: str
    claim_object: str
    evidence_standard_met: bool
    evidence_standard_met_reason: str
    risk_flags: List[str]
    issue_type: str
    object_part: str
    claim_status: str
    claim_status_justification: str
    supporting_image_ids: List[str]
    valid_image: bool
    severity: str


class ClaimVerifyResponse(BaseModel):
    provider: Provider
    prediction: ClaimPrediction


class BatchVerifyRequest(BaseModel):
    claims: List[ClaimVerifyRequest] = Field(..., min_length=1, max_length=100)
    provider: Optional[Provider] = Field(
        default=None, description="Overrides per-claim provider when set."
    )


class BatchItemResult(BaseModel):
    index: int
    ok: bool
    prediction: Optional[ClaimPrediction] = None
    error: Optional[str] = None


class BatchVerifyResponse(BaseModel):
    provider: Provider
    total: int
    succeeded: int
    failed: int
    results: List[BatchItemResult]


class SampleCase(BaseModel):
    case_id: str
    split: str                       # "sample" (labeled) | "test" (unlabeled)
    user_id: str
    claim_object: str
    user_claim: str
    image_paths: List[str]
    labeled: bool
    expected: Optional[dict] = None  # ground-truth output columns (sample split only)


class SamplesResponse(BaseModel):
    split: str
    count: int
    cases: List[SampleCase]


class ProviderInfo(BaseModel):
    provider: str
    model: str
    mock: bool
    operational: bool
    is_default: bool


class ProvidersResponse(BaseModel):
    default_provider: str
    providers: List[ProviderInfo]


class HealthResponse(BaseModel):
    status: str
    reference_data: dict
    config: dict


class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None
