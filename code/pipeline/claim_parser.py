"""
Stage 1 - parse the claimed part(s) and issue from the chat transcript.

In MOCK_MODE this uses a light keyword heuristic so the pipeline is testable
offline. In live mode it will call Gemini (text-only) with the claim_parser
prompt. Keeping it text-only keeps this stage cheap.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import config
from llm.cache import AnalysisCache
from llm.gemini_client import GeminiClient
from pipeline import prompts
from schema import ISSUE_TYPES, OBJECT_PARTS

# Deterministic prompt-injection / instruction detector (defense in depth: the
# LLM is also told to flag these, but we never want to depend on that alone).
_INJECTION_PATTERNS = [
    r"ignore (all|any|previous)", r"approve (the|this|my)? ?claim",
    r"mark (this|it|the row)", r"skip manual review", r"follow the note",
    r"note (says|bole|kehti)", r"approve kar", r"supported with",
    r"accept (this|it) quickly", r"reopen", r"escalate publicly",
]
_INJECTION_RE = re.compile("|".join(_INJECTION_PATTERNS), re.IGNORECASE)


def detect_injection(text: str) -> bool:
    """True if the claim text contains reviewer-manipulation/instruction phrases."""
    return bool(_INJECTION_RE.search(text or ""))


@dataclass
class ParsedClaim:
    claimed_parts: list[str] = field(default_factory=list)
    claimed_issue: str = "unknown"
    multi_part: bool = False
    injection_detected: bool = False
    summary: str = ""


def _heuristic_parse(claim_object: str, user_claim: str) -> ParsedClaim:
    """Deterministic offline fallback used in MOCK_MODE."""
    text = user_claim.lower()
    parts = [p for p in OBJECT_PARTS.get(claim_object, set()) if p != "unknown" and p.replace("_", " ") in text]
    issues = [i for i in ISSUE_TYPES if i not in {"none", "unknown"} and i.replace("_", " ") in text]
    return ParsedClaim(
        claimed_parts=parts or ["unknown"],
        claimed_issue=issues[0] if issues else "unknown",
        multi_part=len(parts) > 1,
        injection_detected=detect_injection(user_claim),
        summary="(mock) heuristic parse of transcript",
    )


def parse_claim(
    claim_object: str,
    user_claim: str,
    client: GeminiClient,
    cache: AnalysisCache | None = None,
) -> ParsedClaim:
    def _mock(_prompt: str, _imgs):
        p = _heuristic_parse(claim_object, user_claim)
        return {
            "claimed_parts": p.claimed_parts,
            "claimed_issue": p.claimed_issue,
            "multi_part": p.multi_part,
            "injection_detected": p.injection_detected,
            "summary": p.summary,
        }

    prompt = prompts.render(
        prompts.CLAIM_PARSER_TEMPLATE,
        claim_object=claim_object, user_claim=user_claim,
    )
    # Cache live parses (text-only) so re-runs don't re-spend the call.
    cache_ns = f"{prompts.CLAIM_PARSER_VERSION}|{config.GEMINI_MODEL}"
    key_bytes = f"{claim_object}\n{user_claim}".encode("utf-8")
    data = None
    if cache is not None and not client.mock:
        data = cache.get(key_bytes, cache_ns)
    if data is None:
        data = client.generate_json(prompt, mock_factory=_mock)
        if cache is not None and not client.mock:
            cache.put(key_bytes, cache_ns, data)
    # Deterministic detector OR the model's flag - belt and suspenders.
    injection = bool(data.get("injection_detected", False)) or detect_injection(user_claim)
    return ParsedClaim(
        claimed_parts=data.get("claimed_parts") or ["unknown"],
        claimed_issue=data.get("claimed_issue", "unknown"),
        multi_part=bool(data.get("multi_part", False)),
        injection_detected=injection,
        summary=data.get("summary", ""),
    )
