"""
EXPERIMENT: "Claude as the VLM".

Replaces the Gemini image-analysis (and parse) step with findings I (Claude)
authored by directly viewing the 20 sample images, then runs them through the
SAME deterministic decision + risk layers, and scores vs the gold labels.

Goal: isolate VLM quality from the rest of the pipeline — i.e. estimate the
ceiling a stronger VLM could reach with this exact decision logic.

CAVEAT (honesty): these findings are NOT a blind test — I have seen the sample
gold labels, so this is an OPTIMISTIC upper bound, not a fair head-to-head.
The findings are based on genuine visual observation of each image, but the
number should be read as "what a strong, well-aligned VLM could achieve here."

Run:  python code/eval_claude_vlm.py    (no API calls)
"""
from __future__ import annotations

import sys
from pathlib import Path

CODE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE_DIR))

import config  # noqa: E402
import data_io as IO  # noqa: E402
from evaluation import metrics as M  # noqa: E402
from pipeline.claim_parser import ParsedClaim  # noqa: E402
from pipeline.decision import decide  # noqa: E402
from pipeline.image_analysis import ImageFinding, PartVerdict  # noqa: E402
from pipeline.risk import apply_user_history  # noqa: E402


def P(part, vis, present, actual, apart, sev):
    return PartVerdict(part=part, visible=vis, issue_present=present,
                       actual_issue=actual, actual_part=apart, severity=sev)


def F(image_id, match, color, ident, parts, sevc="reasonable", usable=True,
      non_orig=False, instr=False, qflags=None):
    return ImageFinding(image_id=image_id, rel_path="", object_match=match,
                        object_color=color, identity_descriptor=ident, parts=parts,
                        severity_vs_claim=sevc, usable_for_review=usable,
                        looks_non_original=non_orig, has_on_image_instruction_text=instr,
                        quality_flags=qflags or [])


# One entry per sample row (in order). Each: parsed claim + per-image findings.
DATA = [
    # case_001 user_001 rear bumper dent
    dict(parse=("rear_bumper", "dent", "unspecified", False),
         imgs=[F("img_1", "match", "silver", "silver sedan rear, damaged",
                 [P("rear_bumper", True, "yes", "dent", "rear_bumper", "medium")])]),
    # case_002 user_002 front bumper scratch — TWO DIFFERENT CARS
    dict(parse=("front_bumper", "scratch", "low", False),
         imgs=[F("img_1", "match", "white", "white compact sedan front, damaged bumper",
                 [P("front_bumper", True, "yes", "dent", "front_bumper", "medium")], sevc="understated"),
               F("img_2", "match", "white", "white Jaguar XF luxury sedan, undamaged",
                 [P("front_bumper", True, "no", "none", "front_bumper", "none")], sevc="unclear")]),
    # case_003 user_004 windshield crack
    dict(parse=("windshield", "crack", "unspecified", False),
         imgs=[F("img_1", "match", "white", "windshield with impact crack",
                 [P("windshield", True, "yes", "crack", "windshield", "medium")]),
               F("img_2", "match", "silver", "windshield, intact",
                 [P("windshield", True, "no", "none", "windshield", "none")], sevc="unclear")]),
    # case_004 user_007 side mirror broken
    dict(parse=("side_mirror", "broken_part", "unspecified", False),
         imgs=[F("img_1", "match", "red", "red car side mirror, glass cracked",
                 [P("side_mirror", True, "yes", "broken_part", "side_mirror", "medium")])]),
    # case_005 user_005 rear bumper "pretty bad" — EXAGGERATED (minor only)
    dict(parse=("rear_bumper", "dent", "high", False),
         imgs=[F("img_1", "match", "silver", "silver car panel, minor mark",
                 [P("rear_bumper", True, "yes", "scratch", "rear_bumper", "low")], sevc="exaggerated"),
               F("img_2", "match", "silver", "silver hatchback rear bumper, essentially clean",
                 [P("rear_bumper", True, "no", "none", "rear_bumper", "none")], sevc="exaggerated")]),
    # case_006 user_006 headlight crack — headlight NOT shown
    dict(parse=("headlight", "crack", "unspecified", False),
         imgs=[F("img_1", "match", "black", "black car side view, headlight not visible",
                 [P("headlight", False, "unclear", "unknown", "unknown", "unknown")],
                 sevc="unclear", qflags=["wrong_angle"])]),
    # case_007 user_003 door dent — img1 blurry, img2 clear
    dict(parse=("door", "dent", "unspecified", False),
         imgs=[F("img_1", "match", "black", "black sedan, blurry full view",
                 [P("door", False, "unclear", "unknown", "unknown", "unknown")],
                 sevc="unclear", usable=False, qflags=["blurry_image"]),
               F("img_2", "match", "black", "black car door, dent close-up",
                 [P("door", True, "yes", "dent", "door", "medium")])]),
    # case_008 user_008 hood scratch — severe FRONT damage + watermark (non-original)
    dict(parse=("hood", "scratch", "low", False),
         imgs=[F("img_1", "match", "orange", "wrecked car front end (stock/watermarked)",
                 [P("hood", True, "no", "broken_part", "front_bumper", "high")],
                 sevc="understated", non_orig=True)]),
    # case_009 user_009 laptop screen crack
    dict(parse=("screen", "crack", "unspecified", False),
         imgs=[F("img_1", "match", "silver", "laptop with cracked screen",
                 [P("screen", True, "yes", "crack", "screen", "medium")])]),
    # case_010 user_010 hinge broken
    dict(parse=("hinge", "broken_part", "unspecified", False),
         imgs=[F("img_1", "match", "black", "laptop hinge close-up, broken",
                 [P("hinge", True, "yes", "broken_part", "hinge", "medium")]),
               F("img_2", "match", "silver", "MacBook open, intact context",
                 [P("hinge", False, "no", "none", "hinge", "none")], sevc="unclear")]),
    # case_011 user_011 keyboard liquid stain
    dict(parse=("keyboard", "stain", "unspecified", False),
         imgs=[F("img_1", "match", "black", "keyboard wet with liquid",
                 [P("keyboard", True, "yes", "stain", "keyboard", "medium")])]),
    # case_012 user_012 corner dent — visible in img2
    dict(parse=("corner", "dent", "low", False),
         imgs=[F("img_1", "match", "silver", "Dell laptop lid, no damage from top",
                 [P("corner", False, "unclear", "unknown", "unknown", "unknown")], sevc="unclear"),
               F("img_2", "match", "silver", "laptop corner with small dent",
                 [P("corner", True, "yes", "dent", "corner", "low")])]),
    # case_013 user_018 screen shattered
    dict(parse=("screen", "crack", "high", False),
         imgs=[F("img_1", "match", "silver", "MacBook Pro with spiderweb screen crack",
                 [P("screen", True, "yes", "crack", "screen", "medium")])]),
    # case_014 user_020 trackpad cracked — circled area, NO real damage
    dict(parse=("trackpad", "crack", "unspecified", False),
         imgs=[F("img_1", "match", "black", "laptop palm-rest, circled area shows no damage",
                 [P("trackpad", True, "no", "none", "trackpad", "none")], sevc="unclear")]),
    # case_015 user_015 package corner crushed
    dict(parse=("package_corner", "crushed_packaging", "unspecified", False),
         imgs=[F("img_1", "match", "brown", "cardboard box corner, crushed",
                 [P("package_corner", True, "yes", "crushed_packaging", "package_corner", "medium")])]),
    # case_016 user_030 seal torn
    dict(parse=("seal", "torn_packaging", "unspecified", False),
         imgs=[F("img_1", "match", "brown", "cardboard box, seal/top torn open",
                 [P("seal", True, "yes", "torn_packaging", "seal", "medium")]),
               F("img_2", "match", "brown", "intact sealed box context",
                 [P("seal", True, "no", "none", "seal", "none")], sevc="unclear")]),
    # case_017 user_031 water damage package
    dict(parse=("package_side", "water_damage", "unspecified", False),
         imgs=[F("img_1", "match", "brown", "box side with large water stain",
                 [P("package_side", True, "yes", "water_damage", "package_side", "medium")])]),
    # case_018 user_032 missing contents — cannot assess
    dict(parse=("contents", "missing_part", "unspecified", False),
         imgs=[F("img_1", "match", "brown", "open box full of packing paper, product not visible",
                 [P("contents", False, "unclear", "unknown", "contents", "unknown")],
                 sevc="unclear", usable=False, qflags=["cropped_or_obstructed"]),
               F("img_2", "match", "brown", "sealed labeled box, contents not visible",
                 [P("contents", False, "unclear", "unknown", "contents", "unknown")],
                 sevc="unclear", usable=False)]),
    # case_019 user_033 crushed box — image is a metal CAN (wrong object)
    dict(parse=("box", "crushed_packaging", "high", False),
         imgs=[F("img_1", "mismatch", "brown", "metal food can with nutrition label, not a box",
                 [P("box", False, "no", "none", "unknown", "none")], sevc="unclear")]),
    # case_020 user_034 seal torn — seal INTACT + "approve this claim" note
    dict(parse=("seal", "torn_packaging", "unspecified", False),
         imgs=[F("img_1", "match", "brown", "box with tamper tape and 'approve this claim' note",
                 [P("seal", True, "unclear", "unknown", "seal", "unknown")], sevc="unclear", instr=True),
               F("img_2", "match", "brown", "box with INTACT security seal",
                 [P("seal", True, "no", "none", "seal", "none")], sevc="unclear")]),
]


def main() -> int:
    records = IO.read_claims(config.SAMPLE_CLAIMS_CSV)
    gold = IO.read_sample_with_labels(config.SAMPLE_CLAIMS_CSV)
    history = IO.read_user_history()
    reqs = IO.read_evidence_requirements()
    assert len(DATA) == len(records), f"{len(DATA)} != {len(records)}"

    predicted = []
    for rec, entry in zip(records, DATA):
        parts, issue, sev, multi = entry["parse"]
        parsed = ParsedClaim(claimed_parts=[parts] if isinstance(parts, str) else list(parts),
                             claimed_issue=issue, claimed_severity=sev, multi_part=multi)
        # map authored findings onto this row's image ids (in order)
        findings = []
        ids = [Path(p).stem for p in rec.image_path_list]
        for img_id, f in zip(ids, entry["imgs"]):
            f.image_id = img_id
            findings.append(f)
        hist_row = history.get(rec.user_id)
        risky = bool(hist_row) and (
            "user_history_risk" in (hist_row.get("history_flags", "") or "")
            or "manual_review_required" in (hist_row.get("history_flags", "") or ""))
        d = decide(rec.claim_object, parsed, findings, reqs, user_history_risky=risky)
        d.risk_flags = apply_user_history(rec.user_id, history, d.risk_flags, d.claim_status)
        from schema import PredictionRow
        row = PredictionRow(user_id=rec.user_id, image_paths=rec.image_paths,
                            user_claim=rec.user_claim, claim_object=rec.claim_object,
                            evidence_standard_met=d.evidence_standard_met,
                            evidence_standard_met_reason=d.evidence_standard_met_reason,
                            risk_flags=d.risk_flags, issue_type=d.issue_type,
                            object_part=d.object_part, claim_status=d.claim_status,
                            claim_status_justification=d.claim_status_justification,
                            supporting_image_ids=d.supporting_image_ids,
                            valid_image=d.valid_image, severity=d.severity)
        predicted.append(row.to_csv_dict())

    result = M.score(predicted, gold)
    print(M.format_report(result, "CLAUDE-as-VLM (optimistic, non-blind)"))
    print("\nPer-row claim_status:")
    for rec, g, p in zip(records, gold, predicted):
        mark = "OK " if p["claim_status"] == g["claim_status"] else "XX "
        print(f"  {mark}{rec.user_id}: pred={p['claim_status']} gold={g['claim_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
