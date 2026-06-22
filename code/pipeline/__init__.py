"""
Four-stage claim-verification pipeline:

  1. claim_parser   - transcript -> claimed part(s) + issue
  2. image_analysis - per-image VLM findings (cached, deduped)
  3. decision       - requirements-aware status / evidence / validity
  4. risk           - user_history -> risk_flags overlay (context only)

The orchestrator `run_pipeline` ties them together for one ClaimRecord.
"""
from code.pipeline.orchestrator import run_pipeline  # noqa: F401
