"""Tests for pipeline/prompts.py - safe render + version extraction."""
from pipeline import prompts


def test_render_substitutes_placeholders():
    out = prompts.render("part={claimed_part} obj={claim_object}",
                         claimed_part="door", claim_object="car")
    assert out == "part=door obj=car"


def test_render_leaves_json_braces_untouched():
    tmpl = 'Context {claim_object}. Output: {\n  "issue_type": "dent"\n}'
    out = prompts.render(tmpl, claim_object="laptop")
    assert '{\n  "issue_type": "dent"\n}' in out
    assert "laptop" in out


def test_templates_have_versions():
    assert prompts.IMAGE_ANALYSIS_VERSION.startswith("image_analysis")
    assert prompts.CLAIM_PARSER_VERSION.startswith("claim_parser")


def test_templates_nonempty():
    assert "{claim_object}" in prompts.IMAGE_ANALYSIS_TEMPLATE
    assert "{user_claim}" in prompts.CLAIM_PARSER_TEMPLATE
