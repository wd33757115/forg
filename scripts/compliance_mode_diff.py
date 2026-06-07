#!/usr/bin/env python3
"""B3: Compare strict / advisory / lenient on the same project state."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from langchain_core.messages import HumanMessage

from forge.agents.compliance import ComplianceAgent
from forge.core.state import create_initial_state
from forge.utils.compliance_explain import summarize_mode_comparison


def _seed_state():
    state = create_initial_state("compliance-mode-diff", current_phase="implementation")
    state["messages"] = [HumanMessage(content="等保三级合规检查与方案校验")]
    state["rule_pack"] = {"protection_level": "3", "pack_id": "system_integration_v1"}
    state["wbs"] = {
        "design": {"name": "设计", "status": "done"},
        "implementation": {"name": "实施", "status": "pending"},
    }
    state["documents"] = [{"title": "技术方案", "doc_type": "方案"}]
    return state


def main() -> int:
    agent = ComplianceAgent()
    base = _seed_state()
    outputs = {}
    for mode in ("strict", "advisory", "lenient"):
        state = dict(base)
        state["check_mode"] = mode
        outputs[mode] = agent.run_compliance(state, skip_react=True)

    summary = summarize_mode_comparison(
        strict=outputs["strict"],
        advisory=outputs["advisory"],
        lenient=outputs["lenient"],
    )

    out_dir = ROOT / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "compliance_mode_diff.md"
    json_path = out_dir / "compliance_mode_diff.json"

    lines = [
        "# Compliance check_mode 对比报告",
        "",
        f"生成时间: {datetime.now(timezone.utc).isoformat()}",
        "",
        "| 模式 | failed_items | matched_rules | compliance_status |",
        "|------|--------------|---------------|-------------------|",
    ]
    for mode, row in summary.items():
        lines.append(
            f"| **{mode}** | {row['failed_count']} | {row['matched_count']} | "
            f"{row['compliance_status']} |"
        )
    lines.extend(["", "## failed_rule_ids", ""])
    for mode, row in summary.items():
        ids = ", ".join(f"`{r}`" for r in row["failed_rule_ids"]) or "—"
        lines.append(f"- **{mode}**: {ids}")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
