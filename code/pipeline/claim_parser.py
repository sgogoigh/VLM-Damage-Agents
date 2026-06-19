"""
Stage 1 - parse the claimed part(s) and issue from the chat transcript.

In MOCK_MODE this uses a light keyword heuristic so the pipeline is testable
offline. In live mode it will call Gemini (text-only) with the claim_parser
prompt. Keeping it text-only keeps this stage cheap.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from llm.gemini_client import GeminiClient
from pipeline import prompts
from schema import ISSUE_TYPES, OBJECT_PARTS


@dataclass
class ParsedClaim:
    claimed_parts: list[str] = field(default_factory=list)
    claimed_issue: str = "unknown"
    multi_part: bool = False
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
        summary="(mock) heuristic parse of transcript",
    )


def parse_claim(claim_object: str, user_claim: str, client: GeminiClient) -> ParsedClaim:
    def _mock(_prompt: str, _imgs):
        p = _heuristic_parse(claim_object, user_claim)
        return {
            "claimed_parts": p.claimed_parts,
            "claimed_issue": p.claimed_issue,
            "multi_part": p.multi_part,
            "summary": p.summary,
        }

    prompt = prompts.render(
        prompts.CLAIM_PARSER_TEMPLATE,
        claim_object=claim_object, user_claim=user_claim,
    )
    data = client.generate_json(prompt, mock_factory=_mock)
    return ParsedClaim(
        claimed_parts=data.get("claimed_parts") or ["unknown"],
        claimed_issue=data.get("claimed_issue", "unknown"),
        multi_part=bool(data.get("multi_part", False)),
        summary=data.get("summary", ""),
    )
