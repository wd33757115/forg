"""Tests for pluggable execution backends."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from forge.config import ForgeSettings, reset_settings_cache
from forge.core.execution.backend import (
    execute_local_manifest,
    execute_webhook,
    resolve_execution_mode,
    run_task_execution,
)
from forge.core.state import create_initial_state


@pytest.fixture
def ready_tasks():
    return [
        {"id": "t1", "status": "ready", "title": "整改A", "task_type": "remediation"},
        {"id": "t2", "status": "draft", "title": "草稿"},
    ]


def test_resolve_execution_mode_state_override():
    state = create_initial_state("exec-mode")
    state["execution_mode"] = "local_manifest"
    assert resolve_execution_mode(state) == "local_manifest"


def test_local_manifest_writes_file(tmp_path, ready_tasks, monkeypatch):
    state = create_initial_state("exec-lm")
    state["run_id"] = "r99"
    settings = ForgeSettings.model_construct(
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
        llm_structured_mode="auto",
        compliance_check_mode="advisory",
        execution_mode="local_manifest",
        execution_manifest_dir=str(tmp_path),
        execution_webhook_url=None,
        execution_webhook_timeout=30.0,
        log_level="WARNING",
        web_host="127.0.0.1",
        web_port=8000,
    )
    import forge.core.execution.backend as backend_mod

    monkeypatch.setattr(backend_mod, "get_settings", lambda: settings)
    updated, results = execute_local_manifest(ready_tasks, state)
    assert updated[0]["status"] == "executed"
    assert len(results) == 1
    manifest_files = list(tmp_path.glob("exec_r99_*.json"))
    assert len(manifest_files) == 1
    payload = json.loads(manifest_files[0].read_text(encoding="utf-8"))
    assert payload["tasks"][0]["id"] == "t1"
    reset_settings_cache()


def test_webhook_fallback_without_url(ready_tasks, monkeypatch):
    state = create_initial_state("exec-wh")
    settings = ForgeSettings.model_construct(
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
        llm_structured_mode="auto",
        compliance_check_mode="advisory",
        execution_mode="webhook",
        execution_manifest_dir="reports/execution",
        execution_webhook_url=None,
        execution_webhook_timeout=30.0,
        log_level="WARNING",
        web_host="127.0.0.1",
        web_port=8000,
    )
    import forge.core.execution.backend as backend_mod

    monkeypatch.setattr(backend_mod, "get_settings", lambda: settings)
    updated, results = execute_webhook(ready_tasks, state)
    assert results[0]["metadata"]["backend"] == "webhook_fallback_simulate"
    reset_settings_cache()


def test_run_task_execution_simulate_default(ready_tasks):
    state = create_initial_state("exec-sim")
    updated, results = run_task_execution(ready_tasks, state)
    assert results[0]["metadata"]["simulated"] is True
    assert updated[0]["status"] == "executed"


def test_webhook_success(ready_tasks, monkeypatch):
    state = create_initial_state("exec-wh-ok")
    settings = ForgeSettings.model_construct(
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
        llm_structured_mode="auto",
        compliance_check_mode="advisory",
        execution_mode="webhook",
        execution_manifest_dir="reports/execution",
        execution_webhook_url="https://example.com/hook",
        execution_webhook_timeout=30.0,
        log_level="WARNING",
        web_host="127.0.0.1",
        web_port=8000,
    )
    import forge.core.execution.backend as backend_mod

    monkeypatch.setattr(backend_mod, "get_settings", lambda: settings)
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    with patch("forge.core.execution.backend.request.urlopen", return_value=mock_resp):
        updated, results = execute_webhook(ready_tasks, state)
    assert results[0]["status"] == "success"
    assert updated[0]["status"] == "executed"
    reset_settings_cache()
