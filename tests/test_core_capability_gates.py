"""CI gates for CORE_CAPABILITY_SCORECARD offline KPIs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from forge.agents.problem_classifier import classify_problem
from forge.utils.core_capability_eval import (
    THRESHOLDS,
    run_offline_evaluation,
    write_evaluation_report,
)

BENCHMARKS = Path(__file__).resolve().parents[1] / "benchmarks"


def test_ps_classification_golden_set():
    data = json.loads((BENCHMARKS / "ps_classification.json").read_text(encoding="utf-8"))
    correct = 0
    for case in data["cases"]:
        hint = case.get("hint")
        ptype, _, _conf = classify_problem(case["question"], hint=hint)
        if ptype == case["expected"]:
            correct += 1
    rate = correct / len(data["cases"])
    assert rate >= data.get("target_accuracy", THRESHOLDS["PS-CLS-01"]), (
        f"PS-CLS-01: {rate:.0%} < {data.get('target_accuracy')}"
    )


def test_offline_scorecard_passes():
    report = run_offline_evaluation()
    assert report.offline_pass, f"Core capability offline gate failed: {report.failures}"


def test_write_evaluation_report(tmp_path):
    report = run_offline_evaluation()
    json_path, md_path = write_evaluation_report(report, out_dir=tmp_path)
    assert json_path.exists()
    assert md_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert "kpis" in payload
    assert len(payload["kpis"]) >= 11
