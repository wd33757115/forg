"""Tests for config and unified LLM module."""

from forge.config import ForgeSettings, get_settings, reset_settings_cache
from forge.utils.llm import get_api_key, resolve_llm_config


def test_settings_defaults():
    reset_settings_cache()
    settings = ForgeSettings()
    assert settings.llm_provider == "deepseek"
    assert settings.llm_max_retries >= 1


def test_resolve_llm_config_without_key(monkeypatch):
    empty = ForgeSettings.model_construct(
        llm_provider="deepseek",
        deepseek_api_key=None,
        openai_api_key=None,
        dashscope_api_key=None,
        aliyun_api_key=None,
        volc_api_key=None,
        ark_api_key=None,
        llm_model=None,
        llm_temperature=0.3,
        llm_max_retries=3,
        llm_retry_delay=1.0,
        llm_timeout=120.0,
    )
    monkeypatch.setattr("forge.utils.llm.get_settings", lambda: empty)
    get_settings.cache_clear()
    assert resolve_llm_config() is None
    assert get_api_key() is None


def test_resolve_aliyun_provider(monkeypatch):
    aliyun = ForgeSettings.model_construct(
        llm_provider="aliyun",
        dashscope_api_key="test-key",
        deepseek_api_key=None,
        openai_api_key=None,
        llm_model=None,
        llm_temperature=0.3,
        llm_max_retries=3,
        llm_retry_delay=1.0,
        llm_timeout=120.0,
    )
    monkeypatch.setattr("forge.utils.llm.get_settings", lambda: aliyun)
    cfg = resolve_llm_config()
    assert cfg is not None
    assert cfg.provider == "aliyun"
    assert "dashscope" in (cfg.base_url or "")
