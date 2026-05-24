import json
from typing import Any, Optional, Type

from pydantic import BaseModel

from vein.config import settings


def has_llm() -> bool:
    return bool(settings.anthropic_api_key) and not settings.demo_mode


def invoke_structured(
    system: str,
    user: str,
    schema: Type[BaseModel],
) -> BaseModel:
    if not has_llm():
        raise RuntimeError("LLM not configured")

    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        temperature=0.2,
    )
    structured = llm.with_structured_output(schema)
    return structured.invoke([SystemMessage(content=system), HumanMessage(content=user)])


def invoke_text(system: str, user: str) -> str:
    if not has_llm():
        raise RuntimeError("LLM not configured")

    from langchain_anthropic import ChatAnthropic
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = ChatAnthropic(
        model=settings.anthropic_model,
        api_key=settings.anthropic_api_key,
        temperature=0.3,
    )
    resp = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    return resp.content if isinstance(resp.content, str) else str(resp.content)


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
