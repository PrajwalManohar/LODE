"""Lightweight input / output guardrails for the LLM-facing endpoints.

These are deliberately simple — pattern-matching only, no LLM-based classifier
— so they run synchronously in the request path and are easy to reason about
in a demo. Returns a GuardrailVerdict; callers decide whether to refuse the
request or sanitise and continue.

Covers, at the demo level:
  * Prompt-injection / jailbreak patterns ("ignore previous instructions", ...)
  * Length cap (defends against runaway prompts)
  * PII in user input (we don't want SSNs flowing to a third-party LLM)
  * Refusal patterns from the LLM output (so they're never logged or stored)

See COMPLIANCE.md for how this maps to the GDPR Art. 32 ("security of
processing") and HIPAA §164.312(c)(1) ("integrity of ePHI") expectations.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from vein.services.privacy import _PATTERNS  # reuse PII regexes

MAX_INPUT_CHARS = 8_000

# Prompt-injection / jailbreak heuristics. Conservative — we want a few
# obvious cases to demo, not to false-positive on real research questions.
_INJECTION_PATTERNS = [
    re.compile(r"\bignore (the )?(previous|above|prior) (instructions|prompt|context)\b", re.I),
    re.compile(r"\bdisregard (the )?system (prompt|message|instructions)\b", re.I),
    re.compile(r"\byou are now (an? )?(?:dan|jailbroken|unrestricted)\b", re.I),
    re.compile(r"\b(reveal|print|leak|exfiltrate) (the )?(system|hidden|secret) prompt\b", re.I),
    re.compile(r"<\|im_start\|>|<\|system\|>", re.I),
]

# Output patterns we don't want to surface or store.
_OUTPUT_LEAK_PATTERNS = [
    re.compile(r"\bAPI[_\s-]?KEY\b\s*[:=]\s*\S+", re.I),
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
]


@dataclass
class GuardrailVerdict:
    """Result from a guardrail check."""
    allowed: bool
    reasons: list[str] = field(default_factory=list)
    sanitized: str | None = None  # cleaned-up version if we chose to continue

    @property
    def refused(self) -> bool:
        return not self.allowed


def check_input(text: str) -> GuardrailVerdict:
    """Inspect a user-supplied LLM input. Returns a verdict the caller acts on."""
    reasons: list[str] = []
    if not isinstance(text, str):
        return GuardrailVerdict(allowed=True)

    if len(text) > MAX_INPUT_CHARS:
        reasons.append(f"input exceeds {MAX_INPUT_CHARS}-char cap (got {len(text)})")

    for pat in _INJECTION_PATTERNS:
        if pat.search(text):
            reasons.append("prompt-injection pattern detected")
            break

    # PII in input → we redact rather than refuse. Lab booking talk can include
    # researcher email by design (that's how identity flows through), so this
    # is informational unless explicitly flagged.
    sanitized: str | None = None
    for kind, pat in _PATTERNS:
        if kind in ("SSN", "CARD", "APIKEY") and pat.search(text):
            reasons.append(f"sensitive {kind} pattern in input — redacting before LLM call")
            if sanitized is None:
                sanitized = text
            sanitized = pat.sub(f"[REDACTED:{kind}]", sanitized)

    allowed = not any(r.startswith("prompt-injection") or r.startswith("input exceeds") for r in reasons)
    return GuardrailVerdict(allowed=allowed, reasons=reasons, sanitized=sanitized)


def check_output(text: str) -> GuardrailVerdict:
    """Inspect an LLM-generated response. We never refuse the user here —
    we just sanitise leaked secrets and report what we masked.
    """
    if not isinstance(text, str):
        return GuardrailVerdict(allowed=True)

    reasons: list[str] = []
    sanitized = text
    for pat in _OUTPUT_LEAK_PATTERNS:
        if pat.search(sanitized):
            reasons.append("output secret pattern masked")
            sanitized = pat.sub("[REDACTED:SECRET]", sanitized)

    return GuardrailVerdict(
        allowed=True,
        reasons=reasons,
        sanitized=sanitized if reasons else None,
    )
