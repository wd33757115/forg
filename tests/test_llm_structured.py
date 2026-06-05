"""Tests for LLM structured output fallbacks."""

import json

import pytest

from forge.agents.solution_output import SolutionOutput
from forge.utils.llm import (
    _is_structured_format_unsupported,
    parse_json_to_model,
    resolve_structured_mode,
)


def test_structured_format_unsupported_detection():
    exc = Exception("Error 400: This response_format type is unavailable now")
    assert _is_structured_format_unsupported(exc) is True


def test_resolve_structured_mode_deepseek():
    from forge.config import ForgeSettings

    settings = ForgeSettings.model_construct(
        llm_provider="deepseek",
        llm_structured_mode="auto",
        deepseek_api_key=None,
        openai_api_key=None,
        dashscope_api_key=None,
        aliyun_api_key=None,
        volc_api_key=None,
        ark_api_key=None,
        llm_model=None,
        llm_temperature=0.3,
        llm_max_retries=0,
        llm_retry_delay=0.0,
        llm_timeout=5.0,
        openai_base_url=None,
        log_level="WARNING",
        web_host="127.0.0.1",
        web_port=8000,
    )
    import forge.utils.llm as llm_mod

    original = llm_mod.get_settings
    llm_mod.get_settings = lambda: settings  # type: ignore[method-assign]
    try:
        assert resolve_structured_mode("deepseek") == "json_prompt"
    finally:
        llm_mod.get_settings = original  # type: ignore[method-assign]


def test_parse_json_to_model_from_fence():
    payload = {
        "problem_type": "security",
        "problem_analysis": "auth failure",
        "root_causes": ["cert expired"],
        "rule_pack_references": [],
        "solutions": [
            {
                "id": "sol-a",
                "title": "fix",
                "description": "d",
                "approach": "a",
                "trade_offs": [],
                "compliance_impact": "c",
                "itil_guidance": "i",
                "estimated_effort": "low",
                "risk_level": "low",
            },
            {
                "id": "sol-b",
                "title": "alt",
                "description": "d2",
                "approach": "a2",
                "trade_offs": [],
                "compliance_impact": "c2",
                "itil_guidance": "i2",
                "estimated_effort": "medium",
                "risk_level": "medium",
            },
        ],
        "recommended_solution_id": "sol-a",
        "next_actions": ["step1"],
        "dengbao_considerations": [],
        "itil_considerations": [],
    }
    text = "```json\n" + json.dumps(payload, ensure_ascii=False) + "\n```"
    result = parse_json_to_model(text, SolutionOutput)
    assert result.problem_type == "security"
    assert result.recommended_solution_id == "sol-a"
