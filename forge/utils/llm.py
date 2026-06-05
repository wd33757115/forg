"""Unified LLM client — multi-provider, retries, structured output."""

from __future__ import annotations

import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Sequence, TypeVar

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from forge.config import ForgeSettings, LLMProvider, get_settings
from forge.utils.logger import get_logger

logger = get_logger("llm")

T = TypeVar("T", bound=BaseModel)

# OpenAI-compatible provider profiles
_PROVIDER_DEFAULTS: dict[LLMProvider, dict[str, Any]] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
        "key_fields": ("deepseek_api_key", "openai_api_key"),
    },
    "openai": {
        "base_url": None,
        "default_model": "gpt-4o-mini",
        "key_fields": ("openai_api_key",),
    },
    "aliyun": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "key_fields": ("dashscope_api_key", "aliyun_api_key", "openai_api_key"),
    },
    "volcengine": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "default_model": "doubao-pro-32k",
        "key_fields": ("volc_api_key", "ark_api_key", "openai_api_key"),
    },
}


@dataclass(frozen=True)
class LLMConfig:
    """Resolved LLM connection parameters."""

    provider: LLMProvider
    api_key: str
    model: str
    base_url: str | None
    temperature: float
    max_retries: int
    retry_delay: float
    timeout: float


class LLMError(Exception):
    """Raised when LLM calls fail after retries."""


class LLMNotConfiguredError(LLMError):
    """No API key / provider configuration available."""


def _resolve_api_key(settings: ForgeSettings, provider: LLMProvider) -> str | None:
    profile = _PROVIDER_DEFAULTS[provider]
    for field in profile["key_fields"]:
        value = getattr(settings, field, None)
        if value and str(value).strip():
            return str(value).strip()
    return None


def resolve_llm_config(
    *,
    temperature: float | None = None,
    model: str | None = None,
    provider: LLMProvider | None = None,
) -> LLMConfig | None:
    """Build resolved LLM config from settings; None if no API key."""
    settings = get_settings()
    prov = provider or settings.llm_provider
    api_key = _resolve_api_key(settings, prov)
    if not api_key:
        return None

    profile = _PROVIDER_DEFAULTS[prov]
    resolved_model = model or settings.llm_model or profile["default_model"]
    base_url = settings.openai_base_url or profile["base_url"]

    return LLMConfig(
        provider=prov,
        api_key=api_key,
        model=resolved_model,
        base_url=base_url,
        temperature=temperature if temperature is not None else settings.llm_temperature,
        max_retries=settings.llm_max_retries,
        retry_delay=settings.llm_retry_delay,
        timeout=settings.llm_timeout,
    )


def get_api_key() -> str | None:
    """Return API key for the configured provider."""
    settings = get_settings()
    return _resolve_api_key(settings, settings.llm_provider)


def get_deepseek_api_key() -> str | None:
    """Backward-compatible alias."""
    settings = get_settings()
    return settings.deepseek_api_key or settings.openai_api_key


@lru_cache(maxsize=16)
def get_llm(
    model: str | None = None,
    temperature: float | None = None,
    provider: LLMProvider | None = None,
) -> BaseChatModel | None:
    """
    Return a chat model for the configured provider, or None if no API key.

    Supports DeepSeek, OpenAI, Aliyun DashScope, Volcengine Ark (OpenAI-compatible).
    """
    config = resolve_llm_config(temperature=temperature, model=model, provider=provider)
    if config is None:
        return None

    kwargs: dict[str, Any] = {
        "model": config.model,
        "api_key": config.api_key,
        "temperature": config.temperature,
        "timeout": config.timeout,
        "max_retries": 0,  # we handle retries at forge layer
    }
    if config.base_url:
        kwargs["base_url"] = config.base_url

    logger.debug(
        "LLM client | provider=%s model=%s base_url=%s",
        config.provider,
        config.model,
        config.base_url or "default",
    )
    return ChatOpenAI(**kwargs)


def _is_retryable(exc: Exception) -> bool:
    """Heuristic: retry transient API / rate-limit errors."""
    msg = str(exc).lower()
    retry_signals = (
        "rate limit",
        "timeout",
        "timed out",
        "connection",
        "503",
        "502",
        "429",
        "overloaded",
        "temporarily",
    )
    return any(s in msg for s in retry_signals)


def invoke_with_retry(
    llm: BaseChatModel,
    messages: Sequence[BaseMessage],
    *,
    max_retries: int | None = None,
    retry_delay: float | None = None,
) -> Any:
    """Invoke chat model with simple exponential backoff on transient errors."""
    settings = get_settings()
    attempts = (max_retries if max_retries is not None else settings.llm_max_retries) + 1
    delay = retry_delay if retry_delay is not None else settings.llm_retry_delay
    last_exc: Exception | None = None

    for attempt in range(attempts):
        try:
            return llm.invoke(messages)
        except Exception as exc:
            last_exc = exc
            if attempt >= attempts - 1 or not _is_retryable(exc):
                logger.warning("LLM invoke failed (attempt %d/%d): %s", attempt + 1, attempts, exc)
                raise LLMError(str(exc)) from exc
            wait = delay * (2**attempt)
            logger.warning(
                "LLM transient error (attempt %d/%d), retry in %.1fs: %s",
                attempt + 1,
                attempts,
                wait,
                exc,
            )
            time.sleep(wait)

    raise LLMError("LLM invoke failed") from last_exc


def escape_braces_for_format(text: str) -> str:
    """Escape ``{`` / ``}`` so user/tool context can be embedded in str.format templates."""
    return text.replace("{", "{{").replace("}", "}}")


def invoke_llm(
    system: str,
    user: str,
    *,
    temperature: float | None = None,
    model: str | None = None,
) -> str | None:
    """Convenience wrapper: returns LLM text or None if unavailable / failed."""
    llm = get_llm(temperature=temperature, model=model)
    if llm is None:
        return None
    try:
        response = invoke_with_retry(
            llm,
            [SystemMessage(content=system), HumanMessage(content=user)],
        )
        return str(response.content)
    except LLMError as exc:
        logger.warning("invoke_llm failed, returning None: %s", exc)
        return None


def invoke_structured_output(
    schema: type[T],
    messages: Sequence[BaseMessage],
    *,
    temperature: float | None = None,
    model: str | None = None,
) -> T | None:
    """
    Invoke LLM with structured output (Pydantic schema).

    Returns parsed model instance, or None if LLM unavailable or all retries fail.
    """
    llm = get_llm(temperature=temperature, model=model)
    if llm is None:
        return None
    try:
        structured = llm.with_structured_output(schema)
        result = invoke_with_retry(structured, messages)
        if isinstance(result, schema):
            return result
        return None
    except LLMError as exc:
        logger.warning("invoke_structured_output failed: %s", exc)
        return None
    except Exception as exc:
        logger.warning("invoke_structured_output parse error: %s", exc)
        return None


def invoke_react_agent(agent: Any, input_state: dict[str, Any]) -> dict[str, Any]:
    """Invoke a LangGraph ReAct agent with retry on transient LLM errors."""
    settings = get_settings()
    attempts = settings.llm_max_retries + 1
    delay = settings.llm_retry_delay
    last_exc: Exception | None = None

    for attempt in range(attempts):
        try:
            return agent.invoke(input_state)
        except Exception as exc:
            last_exc = exc
            if attempt >= attempts - 1 or not _is_retryable(exc):
                logger.warning("ReAct agent failed: %s", exc)
                raise
            wait = delay * (2**attempt)
            logger.warning("ReAct retry in %.1fs: %s", wait, exc)
            time.sleep(wait)

    raise LLMError("ReAct agent failed") from last_exc
