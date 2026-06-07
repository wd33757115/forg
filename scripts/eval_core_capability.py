#!/usr/bin/env python3
"""Evaluate ProblemSolver + Compliance core capability scorecard (offline)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from forge.utils.core_capability_eval import run_offline_evaluation, write_evaluation_report


def main() -> int:
    report = run_offline_evaluation()
    json_path, md_path = write_evaluation_report(report)
    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    print(f"\nWrote {json_path}")
    print(f"Wrote {md_path}")
    if not report.offline_pass:
        print("\n[FAIL] Offline KPI gate — see failures above", file=sys.stderr)
        return 1
    print("\n[PASS] Offline KPI gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
