"""Route a record (tagged by `_source`, or an explicit source) to its normalizer.

Mirrors the dispatch in `modules/data_simulation/generator/schemas/render.py` but in
reverse: authentic record -> unified row. The replay streamer adds a `_source` envelope
key; batch file reads pass the source explicitly.
"""
from __future__ import annotations

from modules.data_simulation.generator.model import SRC_CLOUDTRAIL, SRC_IDP, SRC_K8S
from modules.ingest_enrich.normalize import cloudtrail, idp_session, k8s_audit

_NORMALIZERS = {
    SRC_CLOUDTRAIL: cloudtrail.normalize,
    SRC_K8S: k8s_audit.normalize,
    SRC_IDP: idp_session.normalize,
}


def normalize_record(rec: dict, source: str | None = None) -> dict:
    """Normalize one record. `source` overrides the `_source` envelope key if given."""
    src = source or rec.get("_source")
    if src not in _NORMALIZERS:
        raise ValueError(f"unknown source: {src!r}")
    return _NORMALIZERS[src](rec)
