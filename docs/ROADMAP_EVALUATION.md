# Grok 精细版路线图 — 评估与实施状态

> 评估日期：2026-06-06 | 对照仓库当前实现 | 离线测试：172 passed

## 总体结论

**Grok 五阶段计划与 Forge 当前代码高度对齐。** 阶段 1–5 核心交付物**均已实现**；本评估将每项映射到代码锚点，并标注仅存的 §B 可选项。

建议：**无需从零重做**；后续在 §B（向量检索、外部执行对接、Web 产品化）上迭代即可。

---

## 阶段 1 — 核心闭环 + Demo 专业化

| 步骤 | 任务 | 评估 | 代码锚点 |
|------|------|------|----------|
| 1.1 | ProblemSolver 强化 | ✅ 已达标 | `prompts/problem_solver/prompts.py`（≥3 refs、四段式）；`rule_pack_refs.py` |
| 1.2 | Compliance + check_mode | ✅ 已达标 | `utils/check_mode.py`；`docs/COMPLIANCE_CHECK_MODE.md` |
| 1.3 | ToolRegistry 解耦 | ✅ 已达标 | `test_agent_decoupling.py` |
| 1.4 | CLI Demo Rich | ✅ 已达标 | `cli/demo_display.py` — Agent 追踪表、重试时间线、运行摘要 |
| 1.5 | 运行报告增强 | ✅ 已增强 | `utils/report.py` — 关键决策、重试、trace 表 |
| 1.6 | knowledge_helpers | ✅ 已达标 | 多 tag + keywords；ProblemSolver 注入 `prior_cases` |
| 1.7 | ProjectState 字段 | ✅ 已达标 | `confidence_score`、`execution_tasks`、`execution_results`… |
| 1.8 | 单元测试 | ✅ 已达标 | `test_problem_solver`、`test_compliance`、`test_knowledge` |

**DoD 验证**：`.\run.bat --type security --no-feedback`；`make test`

---

## 阶段 2 — 架构收口

| 步骤 | 任务 | 评估 | 代码锚点 |
|------|------|------|----------|
| 2.1 | AgentRegistry | ✅ | `core/agent_registry.py` |
| 2.2 | AgentOutputBase | ✅ | `agents/output_base.py` |
| 2.3 | prompts 整理 | ✅ | `prompts/<agent>/`；`prompts/README.md`；Agent 直引子目录 |
| 2.4 | Supervisor 重构 | ✅ | `core/supervisor_routing.py` |
| 2.5 | pipeline_trace | ✅ | `utils/trace.py` |
| 2.6 | 代码审查 | ✅ | `docs/CODE_REVIEW.md`、`docs/AGENT_CHECKLIST.md` |

---

## 阶段 3 — 半自治 v1.1

| 步骤 | 任务 | 评估 | 代码锚点 |
|------|------|------|----------|
| 3.1 | ConfidenceScorer | ✅ | `core/confidence/` |
| 3.2 | Execution Layer | ✅ | `core/execution/` + `simulate_execution` |
| 3.3 | ApprovalFlow | ✅ | `core/approval/` |
| 3.4 | Supervisor 扩展 | ✅ | PM → Execution → Approval → Finalize |
| 3.5 | 数据模型 | ✅ | `ExecutionTask`、`ExecutionResult`、`ApprovalRequest` |
| 3.6 | CLI 执行模拟 | ✅ | `--auto-approve`；Demo 执行任务/审批面板 |
| 3.7 | Feedback Loop | ✅ | `utils/feedback_loop.py` |

**DoD 验证**：`scripts/demo.ps1 -AutoApprove` 或 `.\run.bat --type security --auto-approve --no-feedback`

---

## 阶段 4 — 知识与记忆

| 步骤 | 任务 | 评估 | 代码锚点 |
|------|------|------|----------|
| 4.1 | KB 结构化 | ✅ | `type`、`source_agent`、`related_rules`、`outcome` |
| 4.2 | 检索增强 | ✅ | keywords 加权；ProblemSolver 调用 |
| 4.3 | 自动沉淀 | ✅ | `utils/knowledge_extract.py` |
| 4.4 | KB CLI | ✅ | `main.py kb search` |
| 4.5 | Memory Graph | ✅ stub | `core/memory/graph.py` |

---

## 阶段 5 — 工程化

| 步骤 | 任务 | 评估 | 代码锚点 |
|------|------|------|----------|
| 5.1 | 集成测试 | ✅ | `test_full_pipeline`、`test_v11_pipeline_integration` |
| 5.2 | Makefile / 脚本 | ✅ | `Makefile`；`scripts/demo.ps1` |
| 5.3 | README | ✅ | 功能表、Demo、Docker、路线图 |
| 5.4 | Docker | ✅ | `Dockerfile`、`docker-compose.yml` |
| 5.5 | 代码审查 | ✅ | `docs/CODE_REVIEW.md` |

---

## 与 Grok 计划的差异说明

| Grok 建议 | Forge 实际 | 说明 |
|-----------|------------|------|
| 删除 legacy `*_prompt.py` | 保留薄重导出 | 避免破坏外部 import；Agent 已直引子目录 |
| 2–3 周/阶段 | 已压缩交付 | 启发式路径 + 离线测试覆盖主闭环 |
| LLM 引用率 ≥70% | 可选 `make test-llm` | 需 API Key，CI 手动触发 |

---

## 推荐下一步（§B）

1. 向量语义检索（`memory/` 包）
2. Web 审批 UI
3. 真实 CMDB/工单 Execution 适配器

详见 `docs/IMPLEMENTATION_PLAN.md` §22.7。
