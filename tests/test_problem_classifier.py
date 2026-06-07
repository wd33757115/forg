"""Tests for problem type classification."""

from forge.agents.problem_classifier import classify_problem, modules_for_problem_type


def test_classify_security():
    ptype, reason, conf = classify_problem("等保三级登录401认证失败")
    assert ptype == "security"
    assert reason
    assert 0.0 <= conf <= 1.0


def test_classify_itil():
    ptype, _, conf = classify_problem("ITIL事件：核心交换机故障导致业务中断")
    assert ptype == "service_management"
    assert conf >= 0.4


def test_classify_mixed():
    ptype, _, conf = classify_problem("等保401故障同时核心交换机中断")
    assert ptype == "mixed"
    assert conf >= 0.5


def test_classify_hint_override():
    ptype, reason, conf = classify_problem("数据库超时", hint="security")
    assert ptype == "security"
    assert "CLI" in reason
    assert conf > 0.8


def test_classify_uncertain_forces_mixed_low_conf():
    """D4: vague signals should yield 'mixed' with low-ish confidence to widen routing/tools."""
    ptype, reason, conf = classify_problem("系统最近有点问题，需要看看")
    assert ptype == "mixed"
    assert conf < 0.60
    assert "不确定" in reason or "mixed" in reason.lower() or "弱" in reason


def test_modules_for_type():
    mods = modules_for_problem_type("security")
    assert "dengbao_2.0" in mods
