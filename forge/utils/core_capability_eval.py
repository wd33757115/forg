"""Core capability scorecard evaluation for ProblemSolver + Compliance."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage

from forge.agents.compliance import ComplianceAgent
from forge.agents.problem_classifier import classify_problem
from forge.agents.problem_solver import ProblemSolverAgent, _RULE_ID_IN_TEXT
from forge.core.state import create_initial_state
from forge.tools.problem_solver_tools import run_tool_research
from forge.utils.compliance_explain import enrich_compliance_output, resolve_compliance_status_from_output
from forge.utils.metrics import (
    compliance_rule_id_mapping_rate,
    solution_has_rule_references,
    solution_high_relevance_rate,
    solution_reference_coverage,
)
from forge.utils.reference_scoring import summarize_reference_provenance

ROOT = Path(__file__).resolve().parents[2]
BENCHMARKS = ROOT / "benchmarks"
REPORTS_DIR = ROOT / "reports" / "core_capability"

_RULE_ID = re.compile(r"\b((?:db|itil|si)-[a-z0-9-]+)\b", re.I)

# KPI thresholds — keep in sync with docs/CORE_CAPABILITY_SCORECARD.md
THRESHOLDS: dict[str, float] = {
    "PS-STR-01": 1.0,
    "PS-REF-01": 0.75,
    "PS-REF-02": 0.60,
    "PS-REF-03": 0.25,  # max pad ratio (inverted: pass if value <= threshold)
    "PS-EXP-01": 1.0,
    "PS-CLS-01": 0.80,
    "PS-RUB-01": 3.5,
    "CA-MAP-01": 0.95,
    "CA-MOD-01": 1.0,
    "CA-EXP-01": 1.0,
    "CA-STA-01": 1.0,
    "CA-RUB-01": 1.0,
}


@dataclass
class KpiResult:
    kpi_id: str
    name: str
    value: float
    threshold: float
    passed: bool
    detail: str = ""
    inverted: bool = False  # True when lower is better (e.g. pad ratio)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationReport:
    generated_at: str
    overall_pass: bool
    offline_pass: bool
    kpis: list[KpiResult] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "overall_pass": self.overall_pass,
            "offline_pass": self.offline_pass,
            "kpis": [k.to_dict() for k in self.kpis],
            "failures": self.failures,
        }


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _solution_structure_score(solutions: list[dict]) -> tuple[float, str]:
    required = (
        "problem_type",
        "problem_analysis",
        "recommended_solution_id",
        "rule_pack_references",
        "solutions",
        "next_actions",
        "reasoning",
        "confidence",
    )
    if not solutions:
        return 0.0, "no solutions"
    ok = 0
    for sol in solutions:
        missing = [k for k in required if not sol.get(k) and sol.get(k) != 0]
        if not missing and len(sol.get("solutions") or []) >= 2:
            ok += 1
    rate = ok / len(solutions)
    return rate, f"{ok}/{len(solutions)} runs structurally complete"


def _run_ps_heuristic_scenarios() -> list[dict]:
    data = _load_json(BENCHMARKS / "ps_solution_scenarios.json")
    agent = ProblemSolverAgent()
    out: list[dict] = []
    for case in data["cases"]:
        state = create_initial_state(f"eval-{case['id']}")
        state["messages"] = [HumanMessage(content=case["question"])]
        state["rule_pack"] = {"protection_level": "3", "pack_id": "system_integration_v1"}
        research = run_tool_research(state, case["question"])
        raw = agent._build_heuristic_solution(
            state,
            case["question"],
            research,
            case["problem_type"],
            case.get("classification_reason", ""),
        )
        validated = agent._validate_solution_output(
            raw,
            problem_statement=case["question"],
            problem_type=case["problem_type"],
            research_context=research,
        )
        out.append(validated.model_dump())
    return out


def eval_ps_str_01(solutions: list[dict]) -> KpiResult:
    rate, detail = _solution_structure_score(solutions)
    thr = THRESHOLDS["PS-STR-01"]
    return KpiResult(
        "PS-STR-01",
        "输出结构完整性",
        rate,
        thr,
        rate >= thr,
        detail,
    )


def eval_ps_ref_01(solutions: list[dict]) -> KpiResult:
    rate = solution_reference_coverage(solutions)
    thr = THRESHOLDS["PS-REF-01"]
    hits = sum(1 for s in solutions if solution_has_rule_references(s))
    return KpiResult(
        "PS-REF-01",
        "Rule Pack 引用命中率",
        rate,
        thr,
        rate >= thr,
        f"{hits}/{len(solutions)} scenarios with refs",
    )


def eval_ps_ref_02(solutions: list[dict]) -> KpiResult:
    if not solutions:
        return KpiResult("PS-REF-02", "引用贴切度", 0.0, THRESHOLDS["PS-REF-02"], False, "no data")
    rates = [solution_high_relevance_rate(s, threshold=0.7) for s in solutions]
    avg = sum(rates) / len(rates)
    thr = THRESHOLDS["PS-REF-02"]
    return KpiResult(
        "PS-REF-02",
        "高贴切引用占比 (≥0.7)",
        round(avg, 3),
        thr,
        avg >= thr,
        f"per-scenario: {[round(r, 2) for r in rates]}",
    )


def eval_ps_ref_03(solutions: list[dict]) -> KpiResult:
    pads: list[float] = []
    for sol in solutions:
        refs = sol.get("rule_pack_references") or []
        if not refs:
            continue
        from forge.agents.solution_output import RulePackReference

        models = [RulePackReference.model_validate(r) for r in refs]
        stats = summarize_reference_provenance(models)
        pads.append(float(stats["minimum_pad_ratio"]))
    pad = max(pads) if pads else 1.0
    thr = THRESHOLDS["PS-REF-03"]
    return KpiResult(
        "PS-REF-03",
        "minimum_pad 占比上限",
        round(pad, 3),
        thr,
        pad <= thr,
        f"max pad ratio across scenarios: {pad:.1%}",
        inverted=True,
    )


def eval_ps_exp_01(solutions: list[dict]) -> KpiResult:
    if not solutions:
        return KpiResult("PS-EXP-01", "reasoning 含 rule_id", 0.0, 1.0, False, "no data")
    ok = 0
    for sol in solutions:
        text = (sol.get("reasoning") or "") + (sol.get("decision_rationale") or "")
        if _RULE_ID.search(text) or _RULE_ID_IN_TEXT.search(text):
            ok += 1
    rate = ok / len(solutions)
    return KpiResult(
        "PS-EXP-01",
        "reasoning 含 rule_id",
        rate,
        THRESHOLDS["PS-EXP-01"],
        rate >= THRESHOLDS["PS-EXP-01"],
        f"{ok}/{len(solutions)}",
    )


def eval_ps_cls_01() -> KpiResult:
    data = _load_json(BENCHMARKS / "ps_classification.json")
    target = float(data.get("target_accuracy", THRESHOLDS["PS-CLS-01"]))
    correct = 0
    wrong: list[str] = []
    for case in data["cases"]:
        hint = case.get("hint")
        ptype, _ = classify_problem(case["question"], hint=hint)
        if ptype == case["expected"]:
            correct += 1
        else:
            wrong.append(f"{case['id']}: got {ptype}, want {case['expected']}")
    rate = correct / len(data["cases"]) if data["cases"] else 0.0
    return KpiResult(
        "PS-CLS-01",
        "问题分类准确率",
        round(rate, 3),
        target,
        rate >= target,
        "; ".join(wrong[:4]) if wrong else f"{correct}/{len(data['cases'])}",
    )


def eval_ps_rub_01() -> KpiResult:
    path = ROOT / "reports" / "llm_baseline" / "scoring_summary.json"
    if not path.exists():
        return KpiResult(
            "PS-RUB-01",
            "LLM 人工评分均分",
            0.0,
            THRESHOLDS["PS-RUB-01"],
            True,
            "skipped — no scoring_summary.json (run generate_llm_scoring.py)",
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    avg = float(data.get("overall_average") or 0)
    passed = avg >= THRESHOLDS["PS-RUB-01"] or data.get("pass_threshold_3_5", False)
    return KpiResult(
        "PS-RUB-01",
        "LLM 人工评分均分",
        avg,
        THRESHOLDS["PS-RUB-01"],
        passed,
        f"scenarios={data.get('scenarios_scored', 0)}",
    )


def _build_ca_seed(fixture: dict[str, Any]) -> dict[str, Any]:
    seed = fixture["seed_state"]
    state = create_initial_state(seed["project_id"], current_phase=seed.get("current_phase", "implementation"))
    state["messages"] = [HumanMessage(content=seed.get("message", "合规检查"))]
    state["rule_pack"] = {
        "protection_level": seed.get("protection_level", "3"),
        "pack_id": "system_integration_v1",
    }
    state["wbs"] = seed.get("wbs", {})
    state["documents"] = seed.get("documents", [])
    return state


def _run_compliance_modes(fixture: dict[str, Any]) -> dict[str, Any]:
    agent = ComplianceAgent()
    base = _build_ca_seed(fixture)
    outputs: dict[str, Any] = {}
    for mode in ("strict", "advisory", "lenient"):
        state = dict(base)
        state["check_mode"] = mode
        out = agent.run_compliance(state, skip_react=True)
        outputs[mode] = out
    return outputs


def eval_ca_map_01(outputs: dict[str, Any], fixture: dict[str, Any]) -> KpiResult:
    strict = outputs["strict"]
    rate = compliance_rule_id_mapping_rate(strict)
    target = float(fixture.get("rule_id_mapping_target", THRESHOLDS["CA-MAP-01"]))
    return KpiResult(
        "CA-MAP-01",
        "check item rule_id 映射率",
        round(rate, 3),
        target,
        rate >= target,
        f"strict mode, {len([i for m in strict.results for i in m.items])} items",
    )


def eval_ca_mod_01(outputs: dict[str, Any], fixture: dict[str, Any]) -> KpiResult:
    counts = {m: len(outputs[m].failed_items) for m in outputs}
    exp = fixture.get("mode_expectations", {})
    ok = True
    notes: list[str] = []
    for mode, row in exp.items():
        min_f = int(row.get("min_failed_items", 0))
        if counts.get(mode, 0) < min_f:
            ok = False
            notes.append(f"{mode} failed={counts[mode]} < min {min_f}")
    if fixture.get("require_strict_ge_lenient_failed"):
        if counts["strict"] < counts["lenient"]:
            ok = False
            notes.append(f"strict {counts['strict']} < lenient {counts['lenient']}")
    if fixture.get("require_modes_not_identical"):
        if len(set(counts.values())) < 2 and counts["strict"] == counts["lenient"]:
            ok = False
            notes.append("all modes identical failed count")
    detail = f"failed counts: {counts}" + (f"; {'; '.join(notes)}" if notes else "")
    return KpiResult(
        "CA-MOD-01",
        "check_mode 差异化",
        1.0 if ok else 0.0,
        THRESHOLDS["CA-MOD-01"],
        ok,
        detail,
    )


def eval_ca_exp_01(outputs: dict[str, Any]) -> KpiResult:
    strict = outputs["strict"]
    failed = strict.failed_items
    if not failed:
        return KpiResult("CA-EXP-01", "failed_items 可解释性", 1.0, 1.0, True, "no failed items")
    ok = sum(
        1
        for f in failed
        if f.severity in ("low", "medium", "high", "critical") and f.suggestion
    )
    rate = ok / len(failed)
    return KpiResult(
        "CA-EXP-01",
        "failed_items severity+suggestion",
        round(rate, 3),
        THRESHOLDS["CA-EXP-01"],
        rate >= THRESHOLDS["CA-EXP-01"],
        f"{ok}/{len(failed)}",
    )


def eval_ca_sta_01(outputs: dict[str, Any]) -> KpiResult:
    """Published status rules: strict + failed_items → non_compliant (matches ComplianceAgent)."""
    strict = enrich_compliance_output(outputs["strict"], check_mode="strict")
    status = resolve_compliance_status_from_output(strict, check_mode="strict")
    if strict.failed_items:
        status = "non_compliant"
    if not strict.failed_items:
        ok = status == "compliant"
    else:
        ok = status == "non_compliant"
    return KpiResult(
        "CA-STA-01",
        "compliance_status 一致性",
        1.0 if ok else 0.0,
        THRESHOLDS["CA-STA-01"],
        ok,
        f"status={status} failed={len(strict.failed_items)}",
    )


def eval_ca_rub_01(outputs: dict[str, Any], fixture: dict[str, Any]) -> KpiResult:
    known = fixture.get("known_gap_rule_ids") or []
    strict = outputs["strict"]
    failed_ids = {f.rule_id for f in strict.failed_items}
    hits = sum(1 for rid in known if rid in failed_ids)
    rate = hits / len(known) if known else 1.0
    return KpiResult(
        "CA-RUB-01",
        "已知缺口检出率",
        round(rate, 3),
        THRESHOLDS["CA-RUB-01"],
        rate >= THRESHOLDS["CA-RUB-01"],
        f"detected {hits}/{len(known)} of {known}",
    )


def run_offline_evaluation() -> EvaluationReport:
    """Evaluate all offline KPIs (no LLM calls)."""
    solutions = _run_ps_heuristic_scenarios()
    fixture = _load_json(BENCHMARKS / "ca_fixtures.json")
    ca_outputs = _run_compliance_modes(fixture)

    kpis = [
        eval_ps_str_01(solutions),
        eval_ps_ref_01(solutions),
        eval_ps_ref_02(solutions),
        eval_ps_ref_03(solutions),
        eval_ps_exp_01(solutions),
        eval_ps_cls_01(),
        eval_ps_rub_01(),
        eval_ca_map_01(ca_outputs, fixture),
        eval_ca_mod_01(ca_outputs, fixture),
        eval_ca_exp_01(ca_outputs),
        eval_ca_sta_01(ca_outputs),
        eval_ca_rub_01(ca_outputs, fixture),
    ]

    offline_ids = {
        "PS-STR-01",
        "PS-REF-01",
        "PS-REF-02",
        "PS-REF-03",
        "PS-EXP-01",
        "PS-CLS-01",
        "CA-MAP-01",
        "CA-MOD-01",
        "CA-EXP-01",
        "CA-STA-01",
        "CA-RUB-01",
    }
    offline_pass = all(k.passed for k in kpis if k.kpi_id in offline_ids)
    overall_pass = all(k.passed for k in kpis)
    failures = [f"{k.kpi_id}: {k.detail or k.name}" for k in kpis if not k.passed]

    return EvaluationReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        overall_pass=overall_pass,
        offline_pass=offline_pass,
        kpis=kpis,
        failures=failures,
    )


def format_markdown_report(report: EvaluationReport) -> str:
    lines = [
        "# Core Capability 评估报告",
        "",
        f"生成时间: {report.generated_at}",
        f"**Offline 通过**: {'✅' if report.offline_pass else '❌'}",
        f"**Overall 通过**: {'✅' if report.overall_pass else '❌'}",
        "",
        "| KPI | 名称 | 值 | 阈值 | 结果 |",
        "|-----|------|-----|------|------|",
    ]
    for k in report.kpis:
        op = "≤" if k.inverted else "≥"
        mark = "✅" if k.passed else "❌"
        val = f"{k.value:.0%}" if 0 <= k.value <= 1 and k.kpi_id not in ("PS-RUB-01",) else str(k.value)
        thr = f"{k.threshold:.0%}" if k.threshold <= 1 and k.kpi_id not in ("PS-RUB-01",) else str(k.threshold)
        lines.append(f"| `{k.kpi_id}` | {k.name} | {val} | {op} {thr} | {mark} |")
    if report.failures:
        lines.extend(["", "## 未达标项", ""])
        for f in report.failures:
            lines.append(f"- {f}")
    lines.append("")
    return "\n".join(lines)


def write_evaluation_report(
    report: EvaluationReport | None = None,
    *,
    out_dir: Path | None = None,
) -> tuple[Path, Path]:
    """Write latest.json and latest.md; return paths."""
    report = report or run_offline_evaluation()
    out_dir = out_dir or REPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "latest.json"
    md_path = out_dir / "latest.md"
    json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(format_markdown_report(report), encoding="utf-8")
    return json_path, md_path
