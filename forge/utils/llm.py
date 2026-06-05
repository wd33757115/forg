"""Unified LLM client — multi-provider, retries, structured output."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal, Sequence, TypeVar

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ValidationError

from forge.config import ForgeSettings, LLMProvider, get_settings
from forge.utils.logger import get_logger

logger = get_logger("llm")

T = TypeVar("T", bound=BaseModel)

StructuredMode = Literal["auto", "json_schema", "function_calling", "json_prompt"]

# OpenAI-compatible provider profiles
_PROVIDER_DEFAULTS: dict[LLMProvider, dict[str, Any]] = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
        "key_fields": ("deepseek_api_key", "openai_api_key"),
        # DeepSeek API (incl. v3/v4) does not support OpenAI json_schema response_format
        "structured_mode": "json_prompt",
    },
    "openai": {
        "base_url": None,
        "default_model": "gpt-4o-mini",
        "key_fields": ("openai_api_key",),
        "structured_mode": "json_schema",
    },
    "aliyun": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-plus",
        "key_fields": ("dashscope_api_key", "aliyun_api_key", "openai_api_key"),
        "structured_mode": "auto",
    },
    "volcengine": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "default_model": "doubao-pro-32k",
        "key_fields": ("volc_api_key", "ark_api_key", "openai_api_key"),
        "structured_mode": "auto",
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


def resolve_structured_mode(provider: LLMProvider | None = None) -> StructuredMode:
    """Pick structured-output strategy for the active provider."""
    settings = get_settings()
    mode = (settings.llm_structured_mode or "auto").lower()
    if mode in ("json_schema", "function_calling", "json_prompt"):
        return mode  # type: ignore[return-value]
    prov = provider or settings.llm_provider
    return _PROVIDER_DEFAULTS[prov].get("structured_mode", "auto")  # type: ignore[return-value]


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


def _is_structured_format_unsupported(exc: Exception) -> bool:
    """True when the API rejects response_format / json_schema structured output."""
    msg = str(exc).lower()
    signals = (
        "response_format",
        "json_schema",
        "structured output",
        "unavailable now",
        "not supported",
    )
    return any(s in msg for s in signals)


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


def _extract_json_object(text: str) -> str:
    """Pull a JSON object/array from raw LLM text (markdown fences or prose)."""
    raw = text.strip()
    if not raw:
        raise ValueError("empty LLM response")

    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw, re.IGNORECASE)
    if fence:
        raw = fence.group(1).strip()

    for opener, closer in (("{", "}"), ("[", "]")):
        start = raw.find(opener)
        end = raw.rfind(closer)
        if start != -1 and end != -1 and end > start:
            return raw[start : end + 1]
    return raw


def parse_json_to_model(content: str, schema: type[T]) -> T:
    """Parse LLM text into a Pydantic model."""
    payload = json.loads(_extract_json_object(content))
    return schema.model_validate(payload)


def _schema_json_instruction(schema: type[BaseModel]) -> str:
    """Prompt appendix asking for JSON matching the Pydantic schema."""
    schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False, indent=2)
    return (
        "【结构化输出要求】\n"
        "请仅输出一个合法 JSON 对象（不要 Markdown 代码块，不要额外解释）。\n"
        "JSON 必须符合以下 JSON Schema：\n"
        f"{schema_json}"
    )


def _invoke_structured_json_prompt(
    schema: type[T],
    messages: Sequence[BaseMessage],
    llm: BaseChatModel,
) -> T:
    """Fallback: plain chat completion + JSON parse (DeepSeek v4 compatible)."""
    augmented = list(messages) + [HumanMessage(content=_schema_json_instruction(schema))]
    response = invoke_with_retry(llm, augmented)
    content = str(getattr(response, "content", response))
    try:
        return parse_json_to_model(content, schema)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise LLMError(f"JSON parse/validate failed: {exc}") from exc


def _invoke_structured_native(
    schema: type[T],
    messages: Sequence[BaseMessage],
    llm: BaseChatModel,
    *,
    method: str,
) -> T:
    """LangChain with_structured_output (json_schema or function_calling)."""
    structured = llm.with_structured_output(schema, method=method)
    result = invoke_with_retry(structured, messages)
    if isinstance(result, schema):
        return result
    raise LLMError(f"structured output returned unexpected type: {type(result)}")


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

    DeepSeek v4+ rejects OpenAI ``response_format`` json_schema — uses JSON prompt fallback.
    Configure via ``FORGE_LLM_STRUCTURED_MODE`` (auto | json_schema | function_calling | json_prompt).
    """
    config = resolve_llm_config(temperature=temperature, model=model)
    if config is None:
        return None

    llm = get_llm(temperature=temperature, model=model)
    if llm is None:
        return None

    mode = resolve_structured_mode(config.provider)
    chain: list[tuple[str, str]] = []

    if mode == "json_prompt":
        chain = [("json_prompt", "json_prompt")]
    elif mode == "json_schema":
        chain = [("json_schema", "json_schema"), ("json_prompt", "json_prompt")]
    elif mode == "function_calling":
        chain = [
            ("function_calling", "function_calling"),
            ("json_prompt", "json_prompt"),
        ]
    else:  # auto per provider default (deepseek → json_prompt only)
        chain = [("json_prompt", "json_prompt")]

    last_exc: Exception | None = None
    for label, method in chain:
        try:
            if method == "json_prompt":
                logger.debug("structured_output | mode=json_prompt provider=%s", config.provider)
                return _invoke_structured_json_prompt(schema, messages, llm)
            logger.debug("structured_output | mode=%s provider=%s", method, config.provider)
            return _invoke_structured_native(schema, messages, llm, method=method)
        except LLMError as exc:
            last_exc = exc
            if _is_structured_format_unsupported(exc) and method != "json_prompt":
                logger.info(
                    "structured_output %s unsupported, trying fallback: %s",
                    method,
                    exc,
                )
                continue
            logger.warning("invoke_structured_output failed (%s): %s", label, exc)
            return None
        except Exception as exc:
            last_exc = exc
            if _is_structured_format_unsupported(exc):
                logger.info("structured_output %s unsupported, trying json_prompt: %s", method, exc)
                continue
            logger.warning("invoke_structured_output parse error (%s): %s", label, exc)
            return None

    logger.warning("invoke_structured_output exhausted: %s", last_exc)
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
