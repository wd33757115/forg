#!/usr/bin/env python3
"""W1-3: Generate LLM manual scoring JSON from archived run results (rubric-assisted)."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_RULE_ID = re.compile(r"\b((?:db|itil|si)-[a-z0-9-]+)\b", re.I)

DIMENSIONS = [
    "problem_type_correct",
    "rule_pack_relevance",
    "reasoning_followable",
    "solution_actionable",
    "demo_persuasion",
]

SCENARIO_FILES = {
    "security": ROOT / "reports" / "llm_baseline" / "w1-2_security_result.json",
    "itil": ROOT / "reports" / "llm_baseline" / "w1-2_itil_result.json",
    "mixed": ROOT / "reports" / "llm_baseline" / "w1-2_mixed_result.json",
}

EXPECTED_TYPE = {
    "security": "security",
    "itil": "service_management",
    "mixed": "mixed",
}


def _score_problem_type(solution: dict, scenario: str) -> tuple[int, str]:
    actual = solution.get("problem_type", "")
    expected = EXPECTED_TYPE[scenario]
    if actual == expected:
        return 5, f"problem_type={actual} 与场景一致"
    if actual in ("security", "service_management", "mixed", "technical"):
        return 3, f"期望 {expected}，实际 {actual}"
    return 1, f"类型异常: {actual}"


def _score_refs(solution: dict) -> tuple[int, str]:
    refs = solution.get("rule_pack_references") or []
    n = len(refs)
    research = sum(1 for r in refs if r.get("reference_source") == "research")
    if n >= 5 and research >= 3:
        return 5, f"{n} 条引用，{research} 条来自调研"
    if n >= 3:
        return 4, f"{n} 条引用"
    if n >= 1:
        return 2, f"仅 {n} 条引用"
    return 1, "无 Rule Pack 引用"


def _score_reasoning(solution: dict) -> tuple[int, str]:
    text = (solution.get("reasoning") or "") + (solution.get("decision_rationale") or "")
    ids = _RULE_ID.findall(text)
    if len(set(ids)) >= 2:
        return 5, f"reasoning 含 {len(set(ids))} 个 rule_id"
    if ids:
        return 4, f"reasoning 含 rule_id: {ids[0]}"
    analysis = solution.get("problem_analysis") or ""
    if _RULE_ID.search(analysis):
        return 3, "analysis 含 rule_id，reasoning 偏弱"
    return 2, "reasoning 未显式引用 rule_id"


def _score_actionable(solution: dict) -> tuple[int, str]:
    actions = solution.get("next_actions") or []
    sols = solution.get("solutions") or []
    rec = solution.get("recommended_solution_id")
    picked = next((s for s in sols if s.get("id") == rec), None)
    has_approach = bool(picked and picked.get("approach"))
    if len(actions) >= 3 and has_approach:
        return 5, f"{len(actions)} 条 next_actions + 推荐方案有 approach"
    if len(actions) >= 2:
        return 4, f"{len(actions)} 条 next_actions"
    return 2, "行动项偏少"


def _score_persuasion(scores: dict[str, int]) -> tuple[int, str]:
    avg = sum(scores.values()) / len(scores)
    if avg >= 4.5:
        return 5, "各维度均优，可对外演示"
    if avg >= 3.5:
        return 4, "整体可演示，细节可打磨"
    if avg >= 2.5:
        return 3, "勉强可用"
    return 2, "说服力不足"


def score_result(path: Path, scenario: str) -> dict:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    solution = data.get("solution") or data.get("last_solution") or {}
    dim_scores: dict[str, int] = {}
    notes: dict[str, str] = {}

    for dim, fn in [
        ("problem_type_correct", lambda: _score_problem_type(solution, scenario)),
        ("rule_pack_relevance", lambda: _score_refs(solution)),
        ("reasoning_followable", lambda: _score_reasoning(solution)),
        ("solution_actionable", lambda: _score_actionable(solution)),
    ]:
        dim_scores[dim], notes[dim] = fn()

    dim_scores["demo_persuasion"], notes["demo_persuasion"] = _score_persuasion(
        {k: dim_scores[k] for k in dim_scores}
    )
    values = list(dim_scores.values())
    return {
        "scenario": scenario,
        "source": str(path.relative_to(ROOT)).replace("\\", "/"),
        "run_id": data.get("run_id"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reviewer": "rubric-assisted (W1-3)",
        "dimensions": dim_scores,
        "notes": notes,
        "average": round(sum(values) / len(values), 2),
        "pass_threshold_3_5": sum(values) / len(values) >= 3.5,
        "compliance_status": data.get("compliance_status"),
        "rule_pack_ref_count": len(solution.get("rule_pack_references") or []),
    }


def main() -> int:
    out_dir = ROOT / "reports" / "llm_baseline"
    out_dir.mkdir(parents=True, exist_ok=True)
    reports: list[dict] = []
    missing: list[str] = []

    for scenario, path in SCENARIO_FILES.items():
        if not path.is_file():
            missing.append(scenario)
            continue
        report = score_result(path, scenario)
        out_path = out_dir / f"scoring_{scenario}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
            f.write("\n")
        reports.append(report)
        print(f"{scenario}: avg={report['average']} -> {out_path.name}")

    if reports:
        summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scenarios_scored": len(reports),
            "overall_average": round(sum(r["average"] for r in reports) / len(reports), 2),
            "pass_threshold_3_5": all(r["pass_threshold_3_5"] for r in reports),
            "per_scenario": {r["scenario"]: r["average"] for r in reports},
            "missing_scenarios": missing,
        }
        summary_path = out_dir / "scoring_summary.json"
        with summary_path.open("w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    if missing:
        print(f"Missing result files for: {', '.join(missing)}", file=sys.stderr)
        return 1 if not reports else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
