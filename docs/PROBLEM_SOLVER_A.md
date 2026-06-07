# ProblemSolver 深度优化（A 专项）签收说明

> 对应质量收口选项 **A**；基线测试：`tests/test_problem_solver_a.py`  
> 总验收：[`CORE_CAPABILITY_SCORECARD.md`](CORE_CAPABILITY_SCORECARD.md)（PS-* KPI）

## 已实现

| ID | 能力 | 位置 |
|----|------|------|
| A1 | `relevance_score` + 来源统计 | `utils/reference_scoring.py`、`RulePackReference` |
| A2 | ReAct 调研门禁：不足时补 `query_rule_pack` | `utils/react_research_gate.py` |
| A3 | CLI 与自动分类冲突 → `classification_conflict` | `problem_classifier.classify_with_cli_hint` |
| A4 | 置信度前置：引用质量 + 工具证据 | `ProblemSolverAgent._compute_confidence` |
| A5 | 案例检索加权 + Demo 种子 | `knowledge_memory.py`、`scripts/seed_demo_knowledge.py` |
| A6 | 单测 | `tests/test_problem_solver_a.py` |

## 验收命令

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_problem_solver_a.py -q
.\.venv\Scripts\python.exe scripts\seed_demo_knowledge.py
.\run.bat --type security --auto-approve --no-feedback
```

## 观测字段

- `last_solution.rule_pack_references[].relevance_score`
- `reference_provenance`（pad 占比、均分）
- `classification_conflict`（hint 与 auto 不一致时）
- 日志：`Rule Pack refs scored`、`ReAct research gate`

## 目标

- 引用命中率 ≥70%（`test_llm_reference_coverage`）
- `minimum_pad_ratio` 尽量 &lt;20%（`reference_provenance`）
- `relevance_score` 均分随 LLM 路径提升（人工/脚本抽检）
