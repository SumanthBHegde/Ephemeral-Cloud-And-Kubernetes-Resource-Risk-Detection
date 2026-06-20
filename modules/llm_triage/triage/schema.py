"""The triage output contract (design doc §10) — one schema, two uses.

`TRIAGE_SCHEMA` is handed to OpenAI as `response_format` (strict json_schema, so the model is
*forced* to return exactly these 7 fields). `validate_triage()` then re-checks the parsed object with
the stdlib — defence in depth: a strict schema guards the LLM path, the validator also guards the
templated fallback and any cached record, and it is what the retry loop keys off. No pydantic
dependency; `re` + isinstance is enough for 7 fields.
"""
from __future__ import annotations

import re

# the seven §10 fields, in canonical order.
TRIAGE_FIELDS = (
    "likely_intent",
    "confidence",
    "mitre",
    "key_evidence",
    "disambiguation",
    "recommended_guardrails",
)

# MITRE ATT&CK technique id, base or sub-technique (e.g. T1496, T1078.004).
_MITRE_RE = re.compile(r"^T\d{4}(\.\d{3})?$")

# strict json_schema for OpenAI structured outputs. additionalProperties:false + all-required is what
# makes `strict: true` enforce the shape. `incident_id` is set by us, not the model, so it is not here.
TRIAGE_SCHEMA = {
    "name": "incident_triage",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": list(TRIAGE_FIELDS),
        "properties": {
            "likely_intent": {
                "type": "string",
                "description": "One-line classification of the attacker's likely objective.",
            },
            "confidence": {
                "type": "number",
                "description": "Confidence in likely_intent, 0.0-1.0.",
            },
            "mitre": {
                "type": "array",
                "items": {"type": "string"},
                "description": "MITRE ATT&CK technique IDs, e.g. ['T1496', 'T1578'].",
            },
            "key_evidence": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Concrete evidence bullets drawn ONLY from the incident bundle.",
            },
            "disambiguation": {
                "type": "string",
                "description": "Why this is/ isn't the benign look-alike (autoscaler/CI burst).",
            },
            "recommended_guardrails": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Actionable preventative controls.",
            },
        },
    },
}


class ValidationError(ValueError):
    """Raised when a triage object does not satisfy the §10 contract."""


def validate_triage(obj: object) -> dict:
    """Return `obj` unchanged if it is a well-formed triage dict; else raise ValidationError.

    Checks the same constraints the json_schema encodes, plus the MITRE id format and non-empty lists
    (json_schema can't easily express "non-empty"). Used for the LLM retry loop, the fallback, and the
    cache, so every record that reaches the parquet has passed identical validation.
    """
    if not isinstance(obj, dict):
        raise ValidationError(f"triage must be a dict, got {type(obj).__name__}")

    missing = [f for f in TRIAGE_FIELDS if f not in obj]
    if missing:
        raise ValidationError(f"missing fields: {missing}")

    if not isinstance(obj["likely_intent"], str) or not obj["likely_intent"].strip():
        raise ValidationError("likely_intent must be a non-empty string")

    conf = obj["confidence"]
    if isinstance(conf, bool) or not isinstance(conf, (int, float)):
        raise ValidationError("confidence must be a number")
    if not 0.0 <= float(conf) <= 1.0:
        raise ValidationError(f"confidence {conf} out of [0,1]")

    for list_field in ("mitre", "key_evidence", "recommended_guardrails"):
        val = obj[list_field]
        if not isinstance(val, list) or not val:
            raise ValidationError(f"{list_field} must be a non-empty list")
        if not all(isinstance(x, str) and x.strip() for x in val):
            raise ValidationError(f"{list_field} must contain non-empty strings")

    bad_mitre = [t for t in obj["mitre"] if not _MITRE_RE.match(t)]
    if bad_mitre:
        raise ValidationError(f"malformed MITRE ids: {bad_mitre}")

    if not isinstance(obj["disambiguation"], str) or not obj["disambiguation"].strip():
        raise ValidationError("disambiguation must be a non-empty string")

    return obj
