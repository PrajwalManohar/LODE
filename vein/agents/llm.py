"""LLM provider abstraction for LODE.

Supports Google Gemini (primary, default) and Anthropic Claude (fallback or
explicit override). Other modules call `invoke_structured` / `invoke_text` /
`invoke_json` without caring which provider is active.

Provider selection (settings.llm_provider):
  - "google"     → Gemini only (requires GOOGLE_API_KEY)
  - "anthropic"  → Claude only (requires ANTHROPIC_API_KEY)
  - "auto"       → Gemini if GOOGLE_API_KEY set, else Claude
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional, Type

from pydantic import BaseModel

from vein.config import settings

logger = logging.getLogger("vein.llm")


# ---------------------------------------------------------------------------
# Provider selection
# ---------------------------------------------------------------------------
def active_provider() -> Optional[str]:
    """Return the provider name actually wired up, or None if no key is set."""
    if settings.demo_mode:
        return None
    pref = (settings.llm_provider or "auto").lower()
    has_google = bool(settings.google_api_key)
    has_anthropic = bool(settings.anthropic_api_key)
    if pref == "google":
        return "google" if has_google else None
    if pref == "anthropic":
        return "anthropic" if has_anthropic else None
    # auto: prefer google, fall back to anthropic
    if has_google:
        return "google"
    if has_anthropic:
        return "anthropic"
    return None


def has_llm() -> bool:
    return active_provider() is not None


# ---------------------------------------------------------------------------
# Provider builders
# ---------------------------------------------------------------------------
def _build_google(temperature: float = 0.3):
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(
        model=settings.google_model,
        api_key=settings.google_api_key,
        temperature=temperature,
        convert_system_message_to_human=False,
    )


def _build_anthropic(temperature: float = 0.3):
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        temperature=temperature,
    )


def _build_llm(temperature: float = 0.3):
    provider = active_provider()
    if provider == "google":
        return _build_google(temperature=temperature)
    if provider == "anthropic":
        return _build_anthropic(temperature=temperature)
    raise RuntimeError("LLM not configured")


# ---------------------------------------------------------------------------
# Public API — structured / text / json
# ---------------------------------------------------------------------------
def invoke_structured(
    system: str,
    user: str,
    schema: Type[BaseModel],
) -> BaseModel:
    """Return a Pydantic model. Falls back to anthropic if google fails."""
    if not has_llm():
        raise RuntimeError("LLM not configured")

    from langchain_core.messages import HumanMessage, SystemMessage

    msgs = [SystemMessage(content=system), HumanMessage(content=user)]
    try:
        llm = _build_llm(temperature=0.2)
        structured = llm.with_structured_output(schema)
        return structured.invoke(msgs)
    except Exception as exc:  # noqa: BLE001
        logger.warning("primary LLM structured call failed (%s); trying fallback", exc)
        # Fallback path — if google failed and we also have anthropic, retry.
        if active_provider() == "google" and settings.anthropic_api_key:
            try:
                structured = _build_anthropic(temperature=0.2).with_structured_output(schema)
                return structured.invoke(msgs)
            except Exception as exc2:  # noqa: BLE001
                logger.warning("anthropic fallback also failed: %s", exc2)
        raise


def _extract_text(resp) -> str:
    """LangChain responses come back as either a string, a list of content
    blocks (Gemini), or other shapes. Pull out the actual text."""
    c = getattr(resp, "content", resp)
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        parts = []
        for item in c:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                t = item.get("text") or item.get("content") or ""
                if t:
                    parts.append(t)
        if parts:
            return "".join(parts)
    return str(c)


def invoke_text(system: str, user: str, temperature: float = 0.3) -> str:
    if not has_llm():
        raise RuntimeError("LLM not configured")

    from langchain_core.messages import HumanMessage, SystemMessage

    msgs = [SystemMessage(content=system), HumanMessage(content=user)]
    try:
        return _extract_text(_build_llm(temperature=temperature).invoke(msgs))
    except Exception as exc:  # noqa: BLE001
        logger.warning("primary LLM text call failed (%s); trying fallback", exc)
        if active_provider() == "google" and settings.anthropic_api_key:
            try:
                return _extract_text(_build_anthropic(temperature=temperature).invoke(msgs))
            except Exception as exc2:  # noqa: BLE001
                logger.warning("anthropic fallback failed: %s", exc2)
        raise


_JSON_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def invoke_json(system: str, user: str, temperature: float = 0.2) -> Any:
    """Ask the model for JSON and parse it. Best-effort; returns {} on failure.

    Used for prompts where strict Pydantic schemas are too rigid (free-form
    nested lists in SOP / email content). The model is told to respond with
    JSON only; we strip ``` fences before parsing.
    """
    sys = (system or "") + "\n\nRespond with ONLY valid JSON. No prose, no markdown fences."
    try:
        raw = invoke_text(sys, user, temperature=temperature)
    except Exception:
        return {}
    if not raw:
        return {}
    cleaned = _JSON_FENCE.sub("", raw.strip()).strip()
    # Some models still wrap; try to find the first { ... } block.
    if not cleaned.startswith(("{", "[")):
        m = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
        if m:
            cleaned = m.group(1)
    try:
        return json.loads(cleaned)
    except Exception as exc:  # noqa: BLE001
        logger.warning("invoke_json: could not parse model output: %s", exc)
        return {}


# ---------------------------------------------------------------------------
# Citation formatting (unchanged signature; callers depend on this shape)
# ---------------------------------------------------------------------------
def format_citations(chunks: list[dict]) -> list[dict]:
    return [
        {
            "source": c["source"],
            "section": c.get("section", ""),
            "page": c.get("page", ""),
            "excerpt": c["text"][:200] + ("..." if len(c["text"]) > 200 else ""),
        }
        for c in chunks
    ]
