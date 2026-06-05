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
        compliance_check_mode="advisory",
    )


@pytest.fixture(autouse=True)
def _offline_llm(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable real LLM calls in unit tests (heuristic / tool fallback only)."""
    if request.node.get_closest_marker("llm"):
        from forge.utils.env import load_dotenv

        load_dotenv()
        reset_settings_cache()
        yield
        reset_settings_cache()
        return

    from forge.utils import llm as llm_module

    reset_settings_cache()
    if hasattr(llm_module.get_llm, "cache_clear"):
        llm_module.get_llm.cache_clear()
    monkeypatch.setattr(llm_module, "get_settings", _empty_settings)
    monkeypatch.setattr("forge.config.get_settings", _empty_settings)
    monkeypatch.setattr(llm_module, "get_llm", lambda *args, **kwargs: None)
    yield


@pytest.fixture
def require_llm_api_key() -> None:
    """Skip when no real LLM API key is configured (.env or env vars)."""
    from forge.utils import llm as llm_module
    from forge.utils.env import load_dotenv
    from forge.utils.llm import get_api_key

    load_dotenv()
    reset_settings_cache()
    if hasattr(llm_module.get_llm, "cache_clear"):
        llm_module.get_llm.cache_clear()
    if not get_api_key():
        pytest.skip("No LLM API key configured (set DEEPSEEK_API_KEY or FORGE_LLM_PROVIDER in .env)")
