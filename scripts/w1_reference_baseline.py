#!/usr/bin/env python3
"""W1-4: Measure Rule Pack reference provenance for baseline scenarios."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from forge.agents.rule_pack_refs import classify_reference_source, fetch_relevant_rules

SCENARIOS = [
    ("security", "用户登录接口返回401，等保三级身份鉴别", "security"),
    ("itil", "ITIL事件核心交换机中断SLA违约", "service_management"),
    ("mixed", "等保401认证失败同时核心交换机故障中断", "mixed"),
]


def analyze_scenario(name: str, text: str, problem_type: str) -> dict:
    refs = fetch_relevant_rules(problem_type, text, minimum=3, limit=8)
    by_source: dict[str, int] = {}
    items = []
    for ref in refs:
        source = classify_reference_source(ref)
        by_source[source] = by_source.get(source, 0) + 1
        items.append(
            {
                "rule_id": ref.rule_id,
                "module": ref.module,
                "title": ref.title,
                "source": source,
                "relevance": ref.relevance[:80],
            }
        )
    total = len(refs)
    padded = by_source.get("minimum_pad", 0)
    return {
        "scenario": name,
        "problem_type": problem_type,
        "total_refs": total,
        "by_source": by_source,
        "minimum_pad_ratio": round(padded / total, 3) if total else 0.0,
        "refs": items,
    }


def main() -> int:
    out_dir = ROOT / "reports" / "llm_baseline"
    out_dir.mkdir(parents=True, exist_ok=True)

    scenarios = [analyze_scenario(*s) for s in SCENARIOS]
    totals = sum(s["total_refs"] for s in scenarios)
    padded = sum(s["by_source"].get("minimum_pad", 0) for s in scenarios)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "task": "W1-4 reference provenance baseline",
        "scenarios": scenarios,
        "aggregate": {
            "total_refs": totals,
            "minimum_pad_count": padded,
            "minimum_pad_ratio": round(padded / totals, 3) if totals else 0.0,
        },
    }

    stats_path = out_dir / "reference_stats.json"
    with stats_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")

    scoring_template = out_dir / "manual_scoring_template.md"
    if not scoring_template.exists():
        scoring_template.write_text(
            """# W1-3 LLM 人工评分表（模板）

对 security / itil / mixed 三场景各填一份，保存为 `scoring_<scenario>.json`。

| 维度 | 1 | 2 | 3 | 4 | 5 | 得分 |
|------|---|---|---|---|---|------|
| Rule Pack 引用相关性 | | | | | | |
| reasoning 可解释性 | | | | | | |
| 方案可执行性 | | | | | | |
| 合规/ITIL 对齐 | | | | | | |

**均值目标**：≥3.5/5

## 运行 LLM 基线

```powershell
pytest tests/test_llm_reference_coverage.py -m llm -v
```
""",
            encoding="utf-8",
        )

    print(json.dumps(report["aggregate"], ensure_ascii=False, indent=2))
    print(f"Wrote {stats_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
