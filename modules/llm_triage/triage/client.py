"""OpenAI client for the triage agent (design doc §10: strict JSON schema + validation + retry).

`openai` and `dotenv` are imported lazily so the rest of Stage 5 — the fallback path, the cache, the
tests (`--no-llm`) — runs with neither package installed and no API key set. Only `triage_incident`
touches the network.
"""
from __future__ import annotations

import json
import time

from modules.llm_triage.triage import MAX_RETRIES, OPENAI_MODEL, REQUEST_TIMEOUT_S
from modules.llm_triage.triage.prompt import SYSTEM_PROMPT, render_user_prompt
from modules.llm_triage.triage.schema import TRIAGE_SCHEMA, ValidationError, validate_triage

_client = None


def _get_client():
    """Construct (once) an OpenAI client, loading OPENAI_API_KEY from .env if present."""
    global _client
    if _client is None:
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass  # env var may still be set in the shell; openai will error clearly if not.
        from openai import OpenAI
        _client = OpenAI(timeout=REQUEST_TIMEOUT_S)
    return _client


def triage_incident(evidence: dict) -> dict:
    """Call the model on one evidence bundle and return a validated triage dict.

    Strict json_schema forces the shape; we still validate (MITRE format, non-empty lists) and retry on
    transient API errors or any record that fails validation. Raises after MAX_RETRIES so the caller
    can fall back to the template.
    """
    client = _get_client()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": render_user_prompt(evidence)},
    ]
    last_err: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=messages,
                response_format={"type": "json_schema", "json_schema": TRIAGE_SCHEMA},
                temperature=0,
            )
            obj = json.loads(resp.choices[0].message.content)
            return validate_triage(obj)
        except (ValidationError, json.JSONDecodeError) as err:
            last_err = err  # bad output — re-prompt
        except Exception as err:  # transient API / network error
            last_err = err
        if attempt < MAX_RETRIES - 1:
            time.sleep(2 ** attempt)  # 1s, 2s backoff
    raise RuntimeError(f"triage failed after {MAX_RETRIES} attempts: {last_err}")
