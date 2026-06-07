#!/usr/bin/env python3
"""Seed knowledge_base with demo cases so ProblemSolver prior_cases retrieval works (A5)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from forge.core.state import create_initial_state
from forge.utils.knowledge import append_knowledge, append_knowledge_to_state
from forge.utils.knowledge_memory import rebuild_memory_graph

_DEMO_CASES = [
    {
        "agent": "problem_solver",
        "summary": "等保三级登录401：根因为认证服务连接池耗尽，已通过重启与密码策略加固解决。",
        "tags": ["problem_solver", "security", "demo_seed"],
        "category": "problem_solution",
        "outcome": "resolved",
        "related_rules": ["db-acs-001", "db-aud-001"],
    },
    {
        "agent": "problem_solver",
        "summary": "P1 核心交换机故障：按 itil-inc-001 升级，紧急变更恢复，后续双核心冗余立项。",
        "tags": ["problem_solver", "service_management", "demo_seed"],
        "category": "problem_solution",
        "outcome": "compliant",
        "related_rules": ["itil-inc-001", "itil-chg-001", "itil-slm-001"],
    },
    {
        "agent": "problem_solver",
        "summary": "401+交换机并发故障：双轨应急，网络恢复后审计日志从备用源补齐。",
        "tags": ["problem_solver", "mixed", "demo_seed"],
        "category": "problem_solution",
        "outcome": "success",
        "related_rules": ["db-acs-001", "itil-inc-001", "db-bnd-001"],
    },
]


def seed_state(project_id: str = "demo-seed") -> dict:
    state = create_initial_state(project_id, current_phase="implementation")
    state["rule_pack"] = {"pack_id": "system_integration_v1", "protection_level": "3"}
    for case in _DEMO_CASES:
        entry = append_knowledge(
            state,
            agent=case["agent"],
            summary=case["summary"],
            tags=case["tags"],
            category=case["category"],
            detail={"outcome": case["outcome"], "related_rules": case["related_rules"]},
        )
        entry["outcome"] = case["outcome"]
        entry["related_rules"] = case["related_rules"]
        state = {**state, **append_knowledge_to_state(state, entry)}
    state["memory_graph"] = rebuild_memory_graph(state.get("knowledge_base", []))
    return state


def main() -> int:
    out = ROOT / ".forge_state" / "demo_knowledge_seed.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    state = seed_state()
    payload = {
        "project_id": state["project_id"],
        "knowledge_base": state["knowledge_base"],
        "memory_graph": state.get("memory_graph"),
        "seed_cases": len(_DEMO_CASES),
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Seeded {len(_DEMO_CASES)} cases -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
