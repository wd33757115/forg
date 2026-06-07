#!/usr/bin/env python3
"""D2: Evaluate Rule Pack reference quality (causal explanation, specificity, severity alignment).

Runs the standard heuristic scenarios (and LLM scenarios if key available) and
produces a report with per-ref scores:
- relevance_score (existing)
- causal_quality (D2 new)
- has_explicit_cause (bool)
- severity (from pack)
- strict_alignment (bonus when check_mode=strict and high severity)

Also emits a small manual review template.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from forge.agents.problem_classifier import ProblemType
from forge.agents.problem_solver import ProblemSolverAgent
from forge.agents.rule_pack_refs import fetch_relevant_rules
from forge.agents.solution_output import RulePackReference
from forge.core.state import create_initial_state
from forge.tools.problem_solver_tools import run_tool_research
from forge.utils.reference_scoring import (
    score_causal_explanation,
    score_rule_pack_reference,
)

SCENARIOS = [
    ("security", "用户登录接口返回401，等保三级身份鉴别", "security", "strict"),
    ("itil", "ITIL事件核心交换机中断SLA违约", "service_management", "advisory"),
    ("mixed", "等保401认证失败同时核心交换机故障中断", "mixed", "lenient"),
]


def _load_severity() -> dict[str, str]:
    from forge.core.rule_pack import DEFAULT_PACK_FILE, RulePack
    pack = RulePack.load_rule_pack(DEFAULT_PACK_FILE)
    idx = {}
    for mod in pack.modules.values():
        for r in mod.rules:
            idx[r.id] = r.severity or "medium"
    return idx


def analyze_refs(problem_type: ProblemType, text: str, check_mode: str | None) -> list[dict]:
    refs = fetch_relevant_rules(problem_type, text, minimum=3, limit=6, check_mode=check_mode)
    # Also run through the PS enrich path to get scored + causal_quality
    state = create_initial_state("ref-quality")
    state["check_mode"] = check_mode
    agent = ProblemSolverAgent()
    research = run_tool_research(state, text, problem_type=problem_type)
    raw = agent._build_heuristic_solution(state, text, research, problem_type, "eval")
    validated = agent._validate_solution_output(
        raw,
        problem_statement=text,
        problem_type=problem_type,
        research_context=research,
        state=state,
    )
    enriched = validated.rule_pack_references

    sev = _load_severity()
    rows = []
    for r in enriched:
        causal = getattr(r, "causal_quality", score_causal_explanation(r, text))
        rel = score_rule_pack_reference(r, text)
        has_cause = any(m in (r.relevance or "").lower() for m in ("因为", "导致", "对应", "满足", "对齐", "约束"))
        s = sev.get(r.rule_id, "medium")
        strict_bonus = 1 if (check_mode == "strict" and s in ("high", "critical")) else 0
        rows.append({
            "rule_id": r.rule_id,
            "module": r.module,
            "title": r.title,
            "relevance": (r.relevance or "")[:120],
            "relevance_score": round(rel, 2),
            "causal_quality": round(causal, 2),
            "has_explicit_cause": has_cause,
            "severity": s,
            "strict_alignment": strict_bonus,
            "source": r.reference_source or "unknown",
        })
    return rows


def main() -> int:
    out_dir = ROOT / "reports" / "rule_ref_quality"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_rows = {}
    for name, q, ptype, cm in SCENARIOS:
        all_rows[name] = analyze_refs(ptype, q, cm)

    ts = datetime.now(timezone.utc).isoformat()
    payload = {
        "generated_at": ts,
        "scenarios": all_rows,
    }

    json_path = out_dir / "latest.json"
    md_path = out_dir / "latest.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Simple MD report
    lines = ["# Rule Pack Reference Quality Report (D2)", "", f"生成时间: {ts}", ""]
    for name, rows in all_rows.items():
        lines.append(f"## {name}")
        lines.append("| rule_id | sev | rel_score | causal | cause? | source | title |")
        lines.append("|---------|-----|-----------|--------|--------|--------|-------|")
        for r in rows:
            lines.append(
                f"| `{r['rule_id']}` | {r['severity']} | {r['relevance_score']} | "
                f"{r['causal_quality']} | {'Y' if r['has_explicit_cause'] else 'N'} | "
                f"{r['source']} | {r['title'][:40]} |"
            )
        lines.append("")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
