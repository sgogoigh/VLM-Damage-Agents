<!-- PROMPT_VERSION: claim_parser_v1 -->
You extract the structured damage claim from a customer-support chat transcript.
The transcript may be multilingual (e.g. Hindi/English mix). Focus on the FINAL
agreed claim, not earlier hesitations.

## Input
- Object type: {claim_object}
- Conversation transcript:
{user_claim}

## Output STRICT JSON only
{
  "claimed_parts": ["<object_part>", "..."],
  "claimed_issue": "<issue_type or short phrase>",
  "multi_part": false,
  "summary": "<one short sentence of what the user is claiming>"
}

Notes:
- Map parts/issues to the allowed vocabularies when possible.
- If the user explicitly says to focus on / ignore certain photos or parts,
  reflect that in `summary`.
