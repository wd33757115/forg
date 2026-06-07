# Stage 1 签收：核心闭环稳定 + Demo 专业化

> 对应提示词 1.1 – 1.6 | 审计日期：2026-06-07

## 1.1 ProblemSolverAgent ✅

| 要求 | 产出 |
|------|------|
| Prompt：先判类型 + Rule Pack + reasoning/confidence | `prompts/problem_solver/prompts.py` |
| ReAct 注入 knowledge | `search_similar_cases` + `format_memory_context` |
| 引用率兜底 | `ensure_minimum_references`、`_ensure_reasoning_confidence` |
| ToolRegistry | `self.get_tools(state)`，无 `build_*_tools` 直引 |
| 测试 | `test_problem_solver.py`、`test_prompts_abcd.py`、`test_rule_pack_refs_minimum.py` |

## 1.2 ComplianceAgent ✅

| 要求 | 产出 |
|------|------|
| check_mode strict / advisory / lenient | `utils/check_mode.py` + `_normalize_output` |
| rule_id 映射 | `normalize_check_item`、≥80% 映射率测试 |
| matched_rules / failed_items / suggestions | `compliance_output.py` + `enrich_compliance_output` |
| failed_items.severity | high（等保 fail）/ medium / low（warning） |
| check_explanations | `utils/compliance_explain.py` → structured 结果 |
| 测试 | `test_check_mode.py`、`test_compliance.py`、`test_prompts_abcd.py` |

## 1.3 解耦收口 ✅

| 要求 | 产出 |
|------|------|
| 6 Agent → ToolRegistry | `test_agent_decoupling.py` AST 门禁 |
| Prompts → loader | `prompts/loader.py`、`get_prompt()`；`test_prompts_loader.py` |
| 文档 | `docs/AGENT_CHECKLIST.md`、`prompts/README.md` |

## 1.4 CLI Demo 专业化 ✅

| 要求 | 产出 |
|------|------|
| Rich 分块故事板 | `cli/demo_display.py` |
| 合规重试时间线 | `_print_compliance_retry_timeline` |
| 运行报告 + 决策链路 | `utils/report.py` |
| 结束后询问保存报告 | `prompt_save_run_report`（`--no-report-prompt` 可跳过） |

## 1.5 + 1.6 Knowledge & ProjectState ✅

| 要求 | 产出 |
|------|------|
| 多 tag + 关键词加权 | `utils/knowledge.py` `_score_entry` |
| ProblemSolver 注入 | ReAct `prior_cases` |
| memory_graph 闭环 | `knowledge_memory.py`、`knowledge_extract.py` |
| ProjectState v1.1 字段 | `confidence_score`、`risk_level`、`execution_tasks`、`approval_requests` 等 |
| 测试 | `test_knowledge.py`、`test_knowledge_memory.py` |

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q -m "not llm"
.\run.bat --type security --auto-approve --no-feedback
.\run.bat --type security --check-mode strict --report --no-report-prompt
```

## 离线测试基线

**208+** passed（`-m "not llm"`）

## 后续（Stage 2+）

- LLM 路径实测：`pytest tests/test_llm_reference_coverage.py -m llm`
- Execution 外部对接：`FORGE_EXECUTION_MODE=local_manifest|webhook`
- 向量语义检索（非 Stage 1 范围）
