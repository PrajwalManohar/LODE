"""Privacy utilities — PII redaction and an append-only audit log.

Designed to be light enough for the demo while still mapping to the
expectations of GDPR Art. 30 (records of processing), HIPAA §164.312(b)
(audit controls), and FERPA §99.32 (records of disclosure). See COMPLIANCE.md
for the full mapping and the gaps that code alone cannot close.
"""

from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from vein.config import DATA_DIR

AUDIT_DIR = DATA_DIR / "audit"
AUDIT_LOG = AUDIT_DIR / "audit.jsonl"
_lock = threading.Lock()

# ────────────────────────────────────────────────────────────────────────────
# PII patterns — kept conservative so we don't over-redact lab terminology
# (e.g. specimen IDs that look numeric). Covers email / phone / SSN / credit
# card / common API-key prefixes.
# ────────────────────────────────────────────────────────────────────────────
_PATTERNS = [
    ("EMAIL", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("PHONE", re.compile(r"\b(?:\+?\d{1,2}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b")),
    ("SSN",   re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("CARD",  re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("APIKEY", re.compile(r"\b(?:sk|rk|re)_[A-Za-z0-9]{20,}\b")),
]


def redact(text: str) -> str:
    """Return *text* with detected PII replaced by `[REDACTED:<KIND>]`.

    Safe to call on `None`/empty; preserves non-string types untouched.
    """
    if not isinstance(text, str) or not text:
        return text  # type: ignore[return-value]
    out = text
    for kind, pat in _PATTERNS:
        out = pat.sub(f"[REDACTED:{kind}]", out)
    return out


def redact_obj(obj: Any) -> Any:
    """Recursively redact strings inside dicts / lists. Useful for log payloads."""
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, dict):
        return {k: redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_obj(v) for v in obj]
    return obj


# ────────────────────────────────────────────────────────────────────────────
# Audit log — append-only JSONL, one event per line.
# Each row: {"ts","event","actor","subject","detail"}
# `subject` is the user the action *was performed on* (so a self-export logs
# subject=actor, an admin deletion logs subject=<target user>).
# ────────────────────────────────────────────────────────────────────────────
def audit(
    event: str,
    *,
    actor: str | None = None,
    subject: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "event": event,
        "actor": actor,
        "subject": subject,
        "detail": redact_obj(detail or {}),
    }
    line = json.dumps(row, ensure_ascii=False)
    with _lock:
        with AUDIT_LOG.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")


def read_audit(limit: int = 200) -> list[dict[str, Any]]:
    """Return the most recent *limit* audit rows (newest first)."""
    if not AUDIT_LOG.exists():
        return []
    rows: list[dict[str, Any]] = []
    with AUDIT_LOG.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return list(reversed(rows[-limit:]))
