"""Tests for problem type classification."""

from forge.agents.problem_classifier import classify_problem, modules_for_problem_type


def test_classify_security():
    ptype, reason = classify_problem("等保三级登录401认证失败")
    assert ptype == "security"
    assert reason


def test_classify_itil():
    ptype, _ = classify_problem("ITIL事件：核心交换机故障导致业务中断")
    assert ptype == "service_management"


def test_classify_mixed():
    ptype, _ = classify_problem("等保401故障同时核心交换机中断")
    assert ptype == "mixed"


def test_classify_hint_override():
    ptype, reason = classify_problem("数据库超时", hint="security")
    assert ptype == "security"
    assert "CLI" in reason


def test_modules_for_type():
    mods = modules_for_problem_type("security")
    assert "dengbao_2.0" in mods
