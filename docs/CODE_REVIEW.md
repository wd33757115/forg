# Forge 代码审查摘要

> 最近审查：2026-06-07（质量收口 4.3）| 范围：核心 Agent、Supervisor、工具链、可观测性

## 审查结论

| 维度 | 评级 | 说明 |
|------|------|------|
| 架构解耦 | ✅ 良好 | Agent↔Tool 经 Registry；Prompt 经 `loader.py`；路由在 `supervisor_routing.py` |
| 核心智能 | ✅ 良好 | Rule Pack ≥3 引用、`decision_rationale`、Compliance `check_explanations` |
| 可观测性 | ✅ 良好 | pipeline_trace、conversation_history、Run Report、CLI 故事板 |
| 测试覆盖 | ✅ 良好 | 离线 **190** pytest（`-m "not llm"`） |
| 技术债 | 🟡 可控 | 见下方「遗留项」 |

---

## 架构

| 项 | 结论 | 备注 |
|----|------|------|
| Agent–Tool 解耦 | ✅ | 6 Agent 经 `ToolRegistry`；`test_agent_decoupling` AST 门禁 |
| Agent–Prompt 解耦 | ✅ | `prompts/loader.py`；`test_prompts_loader` 禁止直引深层路径 |
| Agent 互引 | ✅ 可接受 | 仅共享 schema（`*_output.py`）与 Compliance 校验 `SolutionOutput` |
| Tools→Agents | ✅ | tools 不 import agent 实现类；`document_tools` 仅用 output schema |
| 工作流组装 | ✅ | `agent_registry.py` + `workflow.py` |
| Supervisor 路由 | ✅ | 条件边在 `supervisor_routing.py`；意图检测在 `supervisor.py` |
| 状态契约 | ✅ | `ProjectState` TypedDict；v1.1 字段完整 |

### 本次修复

- **Supervisor 文档意图误判**：移除宽泛关键词「方案」，避免「处置方案」误入 Document 独立入口（`test_scenarios` 回归）
- **ProblemSolver 冗余兜底**：`ensure_minimum_references` 后删除重复的 `fetch_relevant_rules` 分支

---

## 核心 Agent 质量

| Agent | 结构化输出 | Rule Pack / 追溯 | Handoff |
|-------|------------|------------------|---------|
| ProblemSolver | `SolutionOutput` | `ensure_minimum_references` | `decision_rationale` + refs |
| Compliance | `ComplianceOutput` | `check_explanations` + `rule_id` | 消费 handoff 上下文校验 |
| Security / Operations | ✅ | 工具查询 Rule Pack | specialist 队列 |
| Document / PM | ✅ | 依赖上游 state | 可选降级 |

---

## 可观测性

| 项 | 结论 |
|----|------|
| pipeline_trace | ✅ `input_summary` / `output_summary` / `duration_ms` |
| conversation_history | ✅ thinking / handoff（含 summary）/ compliance_retry |
| 运行报告 | ✅ 决策依据、规则追溯、关键决策、handoff rule_ids |
| CLI Demo | ✅ Rich 故事板 + 合规规则追溯 + 运行统计 |

---

## v1.1 半自治

| 项 | 结论 |
|----|------|
| ConfidenceScorer | ✅ 独立模块，可测试 |
| Execution | ✅ 可插拔后端：`simulate` / `local_manifest` / `webhook`（`core/execution/backend.py`） |
| Approval | ✅ `ApprovalRequest` 状态机 |
| Feedback | ✅ 审批/执行结果写入 knowledge_base |

---

## 测试矩阵

| 类别 | 代表用例 |
|------|----------|
| 解耦门禁 | `test_agent_decoupling`, `test_prompts_loader` |
| 核心逻辑 | `test_problem_solver`, `test_compliance`, `test_rule_pack_refs_minimum` |
| 集成闭环 | `test_scenarios_integration`, `test_v11_pipeline_integration` |
| 可观测性 | `test_report`, `test_trace`, `test_cli_stats` |

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q -m "not llm"
```

---

## 遗留项（非阻塞）

| 项 | 优先级 | 说明 |
|----|--------|------|
| 向量语义检索 | P2 | `knowledge.py` 现为标签/关键词 |
| 真实 Execution 对接 | P2 | `webhook` / `local_manifest` 已就绪；需对接具体 CMDB/工单系统 |
| Web 审批 UI / SSE | P3 | FastAPI 雏形已有 |
| Compliance LLM ReAct | P3 | 闭环默认 `skip_react=True` 求稳；全扫描可走 ReAct |
| 共享 schema 包 | P3 | `*_output.py` 在 `agents/` 下，tools 引用可接受 |

---

## 新增 Agent

见 [`AGENT_CHECKLIST.md`](AGENT_CHECKLIST.md)。

## 相关文档

- 质量收口清单：[`QUALITY_POLISH.md`](QUALITY_POLISH.md)
- 路线图：[`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) §22
