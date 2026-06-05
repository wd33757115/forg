"""DeepSeek LLM client — OpenAI-compatible API."""

from __future__ import annotations

import os
from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI


DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-chat"


def get_deepseek_api_key() -> str | None:
    return os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")


@lru_cache(maxsize=1)
def get_llm(
    model: str = DEFAULT_MODEL,
    temperature: float = 0.3,
) -> BaseChatModel | None:
    """
    Return a DeepSeek chat model, or None if no API key is configured.

    Set DEEPSEEK_API_KEY in environment or .env file.
    """
    api_key = get_deepseek_api_key()
    if not api_key:
        return None
    return ChatOpenAI(
        model=model,
        api_key=api_key,
        base_url=DEEPSEEK_BASE_URL,
        temperature=temperature,
    )


def invoke_llm(system: str, user: str, *, temperature: float = 0.3) -> str | None:
    """Convenience wrapper: returns LLM text or None if unavailable."""
    llm = get_llm(temperature=temperature)
    if llm is None:
        return None
    from langchain_core.messages import HumanMessage, SystemMessage

    response = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    return str(response.content)
