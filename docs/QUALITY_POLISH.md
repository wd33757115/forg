# Forge 质量收口迭代（Quality Polish）

> 目标：核心智能、架构解耦、Demo 可观测性、测试与文档达到**可用、可维护、可扩展**标准。

## 子阶段 1：核心智能能力提升

| 任务 | 状态 | 产出 |
|------|------|------|
| 1.1 ProblemSolver 深度优化 | ✅ | `decision_rationale` 字段、结构化 Prompt 强化、`ensure_minimum_references` |
| 1.2 Rule Pack 引用机制 | ✅ | `rule_pack_refs.ensure_minimum_references()`，合成后 ≥3 条引用 |
| 1.3 Compliance 可解释性 | ✅ | `utils/compliance_explain.py` → `check_explanations` 写入 structured 结果 |
| 1.4 多 Agent handoff | ✅ | `summarize_handoff_payload` 含 rule_ids / decision_rationale |

## 子阶段 2：架构与解耦收口

| 任务 | 状态 | 产出 |
|------|------|------|
| 2.1 ToolRegistry 全面落地 | ✅（前期） | 6/6 Agent 经 `get_tools()` |
| 2.2 Prompts 经 loader 解耦 | ✅ | `forge/prompts/loader.py`，Agent 不再直引深层路径 |
| 2.3 AgentRegistry | ✅（前期） | `core/agent_registry.py` |
| 2.4 AgentOutputBase | ✅（前期） | 各 Agent structured output |
| 2.5 Supervisor 文档化 | ✅（前期） | `supervisor_routing.py` + `IMPLEMENTATION_PLAN.md` |

## 子阶段 3：Demo 与可观测性

| 任务 | 状态 | 产出 |
|------|------|------|
| 3.1 CLI 思考链路 | ✅ | `demo_display`：方案决策依据、handoff summary、合规规则追溯 |
| 3.2 Run Report 增强 | ✅ | 决策依据、check_explanations、handoff rule_ids |
| 3.3 Pipeline Trace | ✅（前期） | `input_summary` / `output_summary` |
| 3.4 Demo 场景脚本 | ✅ | `cli/scenarios.py` 等保 / ITIL / 混合高质量预设 |

## 子阶段 4：测试与代码质量

| 任务 | 状态 | 产出 |
|------|------|------|
| 4.1 核心逻辑测试 | ✅ | `test_compliance_explain`, `test_rule_pack_refs_minimum`, `test_prompts_loader` |
| 4.2 集成测试 | ✅（前期） | `test_v11_pipeline_integration`, `test_full_pipeline` |
| 4.3 代码审查 | ✅ | `docs/CODE_REVIEW.md`（2026-06-07 复审 + 路由/冗余修复） |
| 4.4 文档同步 | ✅ | 本文档 + `prompts/README.md` |

## 验证命令

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -q -m "not llm"
.\run.bat --type security --auto-approve --no-feedback --no-report-prompt
```

## 新增 Agent 接入清单

1. 在 `prompts/<agent>/prompts.py` 定义 Prompt，并注册到 `prompts/loader.py`
2. 在 `core/tool_registry.py` 注册工具
3. 在 `core/agent_registry.py` 注册 Agent 工厂
4. 在 `supervisor_routing.py` 添加路由边
5. 补充 `tests/test_prompts_loader.py` 与 Agent 单元测试
