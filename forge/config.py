"""Forge application settings — loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProvider = Literal["deepseek", "openai", "aliyun", "volcengine"]


def _load_dotenv_safe() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass


class ForgeSettings(BaseSettings):
    """Central configuration for LLM, retries, and runtime behavior."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM provider selection (FORGE_LLM_PROVIDER or LLM_PROVIDER)
    llm_provider: LLMProvider = Field(
        default="deepseek",
        validation_alias=AliasChoices("FORGE_LLM_PROVIDER", "LLM_PROVIDER"),
    )
    llm_model: str | None = Field(default=None, validation_alias="FORGE_LLM_MODEL")
    llm_temperature: float = Field(default=0.3, ge=0.0, le=2.0, validation_alias="FORGE_LLM_TEMPERATURE")
    llm_max_retries: int = Field(default=3, ge=0, le=10, validation_alias="FORGE_LLM_MAX_RETRIES")
    llm_retry_delay: float = Field(default=1.0, ge=0.0, validation_alias="FORGE_LLM_RETRY_DELAY")
    llm_timeout: float = Field(default=120.0, ge=5.0, validation_alias="FORGE_LLM_TIMEOUT")

    # Provider API keys (first non-empty wins per provider)
    deepseek_api_key: str | None = Field(default=None, validation_alias="DEEPSEEK_API_KEY")
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    dashscope_api_key: str | None = Field(default=None, validation_alias="DASHSCOPE_API_KEY")
    aliyun_api_key: str | None = Field(default=None, validation_alias="ALIYUN_API_KEY")
    volc_api_key: str | None = Field(default=None, validation_alias="VOLC_API_KEY")
    ark_api_key: str | None = Field(default=None, validation_alias="ARK_API_KEY")

    # Optional custom OpenAI-compatible endpoint
    openai_base_url: str | None = Field(default=None, validation_alias="OPENAI_BASE_URL")

    # Logging / web
    log_level: str = Field(default="INFO", validation_alias="FORGE_LOG_LEVEL")
    web_host: str = Field(default="127.0.0.1", validation_alias="FORGE_WEB_HOST")
    web_port: int = Field(default=8000, validation_alias="FORGE_WEB_PORT")


@lru_cache(maxsize=1)
def get_settings() -> ForgeSettings:
    """Return cached settings (loads .env on first access)."""
    _load_dotenv_safe()
    return ForgeSettings()


def reset_settings_cache() -> None:
    """Clear settings cache (for tests)."""
    cache_clear = getattr(get_settings, "cache_clear", None)
    if cache_clear is not None:
        cache_clear()
