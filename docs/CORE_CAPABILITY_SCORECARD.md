# Core Capability Scorecard — ProblemSolver + Compliance

> **单一验收来源**：核心能力是否「足够强」以本文件 KPI 红绿为准，不再使用模糊的「再打磨」表述。  
> **一键验收**：`python scripts/eval_core_capability.py` → `reports/core_capability/latest.json`  
> **CI 门禁**：`tests/test_core_capability_gates.py`  
> **关联**：[`PROBLEM_SOLVER_A.md`](PROBLEM_SOLVER_A.md) · [`COMPLIANCE_B.md`](COMPLIANCE_B.md) · [`PATH_A_QUALITY.md`](PATH_A_QUALITY.md)

---

## 1. 使用方式

### 每次改 ProblemSolver / Compliance 之后

```powershell
.\.venv\Scripts\python.exe scripts\eval_core_capability.py
.\.venv\Scripts\python.exe -m pytest tests/test_core_capability_gates.py -q
```

### 有 LLM API Key 时（Prompt 大改后）

```powershell
pytest tests/test_llm_reference_coverage.py -m llm -v
.\.venv\Scripts\python.exe scripts\generate_llm_scoring.py
.\.venv\Scripts\python.exe scripts\eval_core_capability.py
```

### 给 Cursor 的任务模板

```text
目标 KPI：PS-REF-02（当前见 reports/core_capability/latest.json）
约束：只改 forge/agents/problem_solver.py、forge/utils/reference_scoring.py
验收：python scripts/eval_core_capability.py 且 PS-REF-02 变绿
```

---

## 2. KPI 定义

| KPI ID | Agent | 名称 | 目标 | 数据源 |
|--------|-------|------|------|--------|
| **PS-STR-01** | ProblemSolver | 输出结构完整 | 100% | 启发式三场景 `SolutionOutput` |
| **PS-REF-01** | ProblemSolver | 引用命中率 | ≥ 75% | `benchmarks/ps_solution_scenarios.json` |
| **PS-REF-02** | ProblemSolver | 高贴切引用 (score≥0.7) | ≥ 60% 均值 | `reference_scoring` |
| **PS-REF-03** | ProblemSolver | minimum_pad 占比 | ≤ 25% | `reference_provenance` |
| **PS-EXP-01** | ProblemSolver | reasoning 含 rule_id | 100% | regex 门禁 |
| **PS-CLS-01** | ProblemSolver | 分类准确率 | ≥ 80% | `benchmarks/ps_classification.json` |
| **PS-RUB-01** | ProblemSolver | LLM 评分均分 | ≥ 3.5/5 | `reports/llm_baseline/scoring_summary.json` |
| **CA-MAP-01** | Compliance | rule_id 映射率 | ≥ 95% | `metrics.compliance_rule_id_mapping_rate` |
| **CA-MOD-01** | Compliance | 三模式差异化 | strict≥lenient failed | `benchmarks/ca_fixtures.json` |
| **CA-EXP-01** | Compliance | failed_items 可解释 | 100% 有 severity+suggestion | `compliance_explain` |
| **CA-STA-01** | Compliance | status 与 failed 一致 | strict+failed→non_compliant | 状态规则 |
| **CA-RUB-01** | Compliance | 已知缺口检出 | 100% | `known_gap_rule_ids` in fixture |

**Offline 门禁**（CI 每次跑）：除 PS-RUB-01 外全部 KPI。  
**Overall 通过**：含 PS-RUB-01（无 scoring 文件时跳过视为通过）。

---

## 3. 金数据集

| 文件 | 用途 |
|------|------|
| `benchmarks/ps_classification.json` | 12 条分类 golden cases |
| `benchmarks/ps_solution_scenarios.json` | 3 条离线方案场景 |
| `benchmarks/ca_fixtures.json` | Compliance 标准种子 state |

扩展金数据集时：**只加 case，不降低阈值**；若需降阈值须在本文档记录变更理由。

---

## 4. 迭代规则

| 信号 | 动作 |
|------|------|
| Offline KPI 红灯 | 开修复任务，任务描述必须带 KPI ID |
| 同一 KPI 连续 2 次红灯 | 开专项（类似 A/B 专项），限定文件范围 |
| LLM PS-RUB-01 低于 3.5 | 先查 API/结构化，再动 Prompt |
| 全部绿灯 + LLM 4/4 | 可进入 v1.2 功能开发，核心能力进入维护态 |

---

## 5. 实现锚点

| 组件 | 路径 |
|------|------|
| 评估逻辑 | `forge/utils/core_capability_eval.py` |
| CLI 脚本 | `scripts/eval_core_capability.py` |
| 度量函数 | `forge/utils/metrics.py` |
| 引用评分 | `forge/utils/reference_scoring.py` |
| 合规解释 | `forge/utils/compliance_explain.py` |
| 报告输出 | `reports/core_capability/latest.{json,md}` |

---

## 6. 当前基线（签收后更新）

运行 `eval_core_capability.py` 后在此记录：

- Offline：**以 `latest.json` 的 `offline_pass` 为准**
- 测试：`pytest -m "not llm"` 全绿
- LLM：`pytest -m llm` 按需
