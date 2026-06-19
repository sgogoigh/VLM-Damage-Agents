"""End-to-end (mock) tests for pipeline/orchestrator.py + schema validity."""
import config
import data_io as IO
from llm.cache import AnalysisCache
from llm.gemini_client import GeminiClient
from pipeline import run_pipeline
from schema import (
    CLAIM_STATUS, ISSUE_TYPES, OBJECT_PARTS, RISK_FLAGS, SEVERITY,
)


def _run_all(csv_path):
    records = IO.read_claims(csv_path)
    history = IO.read_user_history()
    reqs = IO.read_evidence_requirements()
    client = GeminiClient()
    cache = AnalysisCache()
    return [run_pipeline(r, history=history, requirements=reqs,
                         client=client, cache=cache) for r in records]


def test_pipeline_runs_on_full_test_set():
    preds = _run_all(config.CLAIMS_CSV)
    assert len(preds) == 44


def test_every_output_value_is_in_vocabulary():
    preds = _run_all(config.SAMPLE_CLAIMS_CSV)
    for p in preds:
        d = p.to_csv_dict()
        assert d["claim_status"] in CLAIM_STATUS
        assert d["issue_type"] in ISSUE_TYPES
        assert d["object_part"] in OBJECT_PARTS[d["claim_object"]]
        assert d["severity"] in SEVERITY
        assert d["evidence_standard_met"] in {"true", "false"}
        assert d["valid_image"] in {"true", "false"}
        for flag in d["risk_flags"].split(";"):
            assert flag in RISK_FLAGS


def test_output_preserves_input_echo():
    records = IO.read_claims(config.SAMPLE_CLAIMS_CSV)
    preds = _run_all(config.SAMPLE_CLAIMS_CSV)
    for rec, p in zip(records, preds):
        assert p.user_id == rec.user_id
        assert p.image_paths == rec.image_paths
        assert p.claim_object == rec.claim_object
