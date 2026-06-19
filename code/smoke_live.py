"""
Live smoke test (makes REAL Gemini calls). Not a unit test - run manually:

    python code/smoke_live.py            # first 2 sample claims
    python code/smoke_live.py 3          # first 3 sample claims

Validates the live SDK path end-to-end: claim parse -> per-image VLM analysis
(+cache) -> decision, on real sample images, and prints findings vs expected.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
import data_io as IO
from llm.cache import AnalysisCache
from llm.gemini_client import GeminiClient
from pipeline import run_pipeline


def main(n: int) -> int:
    print(f"[config] {config.summary()}")
    if config.MOCK_MODE:
        print("ERROR: MOCK_MODE is on (no key?). Live smoke needs a real key.")
        return 1

    records = IO.read_claims(config.SAMPLE_CLAIMS_CSV)[:n]
    labels = IO.read_sample_with_labels(config.SAMPLE_CLAIMS_CSV)[:n]
    history = IO.read_user_history()
    reqs = IO.read_evidence_requirements()
    client = GeminiClient()
    cache = AnalysisCache()

    for rec, lab in zip(records, labels):
        print("\n" + "=" * 70)
        print(f"{rec.user_id} | {rec.claim_object} | imgs={len(rec.image_path_list)}")
        pred = run_pipeline(rec, history=history, requirements=reqs,
                            client=client, cache=cache).to_csv_dict()
        slim = {k: pred[k] for k in (
            "evidence_standard_met", "risk_flags", "issue_type", "object_part",
            "claim_status", "supporting_image_ids", "valid_image", "severity")}
        exp = {k: lab[k] for k in slim}
        print("PRED:", json.dumps(slim, ensure_ascii=False))
        print("GOLD:", json.dumps(exp, ensure_ascii=False))
        print("status match:", slim["claim_status"] == exp["claim_status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 2))
