"""Shared pytest fixtures — keep tests offline and deterministic."""

from __future__ import annotations

import pytest

from forge.config import ForgeSettings, reset_settings_cache
from forge.utils.llm import get_llm


def _empty_settings() -> ForgeSettings:
    return ForgeSettings.model_construct(
        llm_provider="deepseek",
        deepseek_api_key=None,
        openai_api_key=None,
        dashscope_api_key=None,
        aliyun_api_key=None,
        volc_api_key=None,
        ark_api_key=None,
        openai_base_url=None,
        llm_model=None,
        llm_temperature=0.3,
        llm_max_retries=0,
        llm_retry_delay=0.0,
        llm_timeout=5.0,
        log_level="WARNING",
        web_host="127.0.0.1",
        web_port=8000,
    )


@pytest.fixture(autouse=True)
def _offline_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable real LLM calls in unit tests (heuristic / tool fallback only)."""
    from forge.utils import llm as llm_module

    reset_settings_cache()
    if hasattr(llm_module.get_llm, "cache_clear"):
        llm_module.get_llm.cache_clear()
    monkeypatch.setattr(llm_module, "get_settings", _empty_settings)
    monkeypatch.setattr("forge.config.get_settings", _empty_settings)
    monkeypatch.setattr(llm_module, "get_llm", lambda *args, **kwargs: None)
    yield
