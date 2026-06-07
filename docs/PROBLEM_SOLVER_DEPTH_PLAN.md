# ProblemSolverAgent 深度工作计划（剩余 ~80%）

基于用户 2026-06-07 拆解的 6 大类，按重要性排序实施。  
**原则**：在不破坏现有可靠性（P0/P1 结构化合规反馈、confidence 安全、specialist 收敛、Scorecard 12 KPI）的前提下，**逐步把“会说话的方案生成器”变成“懂项目、懂规则、会用经验”的智能体**。

## 总体阶段划分（建议 3-4 个迭代）

| 阶段 | 重点类别 | 目标产出 | 验收 |
|------|----------|----------|------|
| **Phase D1（本轮）** | 1 + 5 + 部分 3 | 更深 reasoning + 丰富输出结构 + 更强的历史案例引用 | 新字段存在、prompt 模板更新、启发式+LLM 路径都填充、现有 Scorecard KPI 不降、测试新增深度断言 |
| **Phase D2** | 2 + 部分 1 | Rule Pack 引用质量（自然解释 + check_mode 感知 + 质量钩子） | 引用 relevance 提升、reasoning 显式因果链、简单评估脚本 |
| **Phase D3** | 3 + 6 | 知识真正驱动 + 置信度/风险自评估 + 执行反馈闭环起点 | 案例相似度增强、PS 自己输出 confidence + risks、execution_results 能影响下一次 |
| **Phase D4** | 4 + 收尾 | 分类策略自适应 + 多轮内部推理雏形 + 统一 AgentOutputBase | 路由更准、prompt 条件分支、整体质量人工抽检 |

---

## Phase D1 详细任务（当前正在做）

### 1.1 输出模型扩展（SolutionOutput + 辅助模型）
- 新增字段（全部可选 + 默认空/[]，向后兼容）：
  - `assumptions: list[str]`
  - `risks: list[RiskItem]`（简单 dataclass: title, severity, likelihood, mitigation, related_rule_ids）
  - `alternatives: str`（对其他方案的简要对比与放弃理由）
  - `project_state_snapshot: str`（可选，当前 WBS/阶段关键摘要，便于下游可解释）
- 在 `SolutionOption` 中强化已有 `trade_offs`、`risk_level` 的使用。

### 1.2 Prompt 深度重构（SYSTEM + REACT_TASK + STRUCTURED）
- 明确要求 **结构化 reasoning** 五段式（已在提示中有雏形，进一步强化）：
  1. 问题类型与项目上下文（WBS/阶段/当前风险）
  2. 关键证据（工具 + Rule Pack + 历史案例）
  3. 方案对比（至少 2 个，列出 pros/cons vs rule_id + 成本/风险/合规）
  4. 推荐理由 + 为什么不选其他（explicit alternatives）
  5. 假设（assumptions） + 残余风险（risks） + 监控点
- 强制历史案例**引用具体 id/outcome**（而非泛泛“已参考历史”）。
- 增加对 `get_current_project_state` 返回的 WBS/阶段的**显式分析**要求。
- 保留并强化现有 rule_id / compliance_feedback / prior_cases 门禁。

### 1.3 代码逻辑增强
- `_run_react`：把 project_state 的关键摘要（WBS 状态、当前阶段）更清晰地格式化进 prompt。
- `_validate_solution_output` / 新增 `_enrich_reasoning_depth`：
  - 若 LLM 输出 reasoning 过于平淡，自动结构化为编号 + bullet。
  - 确保 `solutions` 数量 >=2 且有 trade_offs/risk_level。
  - 确保 `risks` / `assumptions` / `alternatives` 在启发式和 LLM 路径都有填充（启发式可从现有 risk_level + trade_offs 合成）。
  - 加强 `_ensure_prior_case_reasoning`：如果 prior_cases 有具体 id/outcome，reasoning 必须出现引用。
- `_build_heuristic_solution`：填充 assumptions、risks、alternatives 摘要。
- 保留 P0 的 confidence 安全（min + heuristic cap）和 solution_source 标记。

### 1.4 知识利用加强（Category 3 起点）
- 改进 `format_memory_context` 或在 PS 内做二次格式化：输出 “案例 ID: xxx | 类似问题 | 采取措施 | 结果 | 相关 rule”。
- 在结构化 prompt 中增加“必须在 reasoning 中引用至少一个历史案例（若相关）”的硬性要求。
- 日志记录“prior_cases 命中数 + 是否被 reasoning 引用”。

### 1.5 可解释性与结构（Category 5）
- reasoning 最终输出尽量使用一致的 Markdown 结构（1. 2. 3. + bullets）。
- 新字段通过 `model_dump` 自然暴露给 Compliance / PM / Report / Demo。
- Demo 和 report 后续可展示 risks / assumptions（不阻塞本阶段）。

### 1.6 验收（不破坏现有）
- 运行 `scripts/eval_core_capability.py` → PS-* KPI 仍全绿（尤其是 PS-REF-01/02/03、PS-EXP-01、PS-CLS-01）。
- `pytest -m "not llm"` 全绿 + 新增 `test_problem_solver_depth.py`（验证新字段存在、启发式填充、reasoning 结构）。
- 至少一个 LLM 场景（若有 key）人工抽查：reasoning 有 5 段、引用了历史案例或明确 alternatives、risks 非空。
- `SolutionOutput` 新字段在 heuristic 和结构化路径都可序列化。

---

## 后续阶段简要

**D2（Rule Pack 深度）**
- 在 fetch / merge 阶段增加 check_mode 偏好（strict 更偏高 severity 条款）。
- 在 reasoning 后处理中强制“rule_id 因果链”句子级检查。
- 增加轻量引用质量打分（除 relevance_score 外，增加 explanation_quality 启发式）。
- 脚本 `scripts/eval_rule_reference_quality.py` + 人工模板。

**D3（知识 + 置信度/风险/闭环）**
- 知识：引入简单 embedding 相似度（或先加强关键词+图 boost）。
- PS 自己产生更丰富的 `risks` 列表 + 置信度理由（`confidence_rationale` 新字段）。
- 执行反馈：`last_execution_results` 进入下一次 PS 的 research_context，影响推荐。
- 低置信度时强制输出 2+ 推荐方案（`recommended_alternatives`）。

**D4（分类 + 多轮 + 统一）**
- 分类器增加置信度 + “不确定时走 mixed + 更多工具”。
- 内部 ReAct 支持轻量 self-critique 循环（或至少 prompt 里的 self-check 步骤）。
- 把 SolutionOutput 基类化或与其它 AgentOutput 做字段对齐（AgentOutputBase 演进）。

---

## 风险与约束

- **不破坏可靠性**：任何深度改动后必须跑 Scorecard + offline 测试。
- **LLM 路径 vs 启发式**：启发式必须也能填充新字段（保证离线测试和无 key 场景可用）。
- **增量**：每次只动 prompt + model + 少量 post-processing，避免大重构。
- **可观测**：新字段要出现在 pipeline_trace / conversation_history / report / demo 中（后续 PR）。

---

## 当前进度标记

- [x] D1 模型扩展 + prompt 模板 + 代码后处理骨架（已完成，先前轮次）
- [x] D1 完整测试 + Scorecard 回归（246 passed，KPI 全绿）
- [x] D2 开始并完成核心切片：
  - fetch_relevant_rules 支持 check_mode + strict 高 severity 偏好
  - apply_relevance_scores 同时产出 causal_quality
  - _ensure_rule_causal_explanation 强制因果链句子
  - 新脚本 scripts/eval_rule_reference_quality.py + reports/rule_ref_quality/
  - 提示词轻微强化（strict 模式优先 high/critical）
  - 验证：eval_core_capability PASS + 246 offline passed

- [ ] D2 完整人工模板 + 更多 check_mode 场景覆盖（后续可扩展）
- [ ] D3 开始（知识利用深化 + 置信度/风险自评估 + 执行反馈）

本计划将持续更新。所有实现必须通过 `eval_core_capability.py` 和现有门禁。

## D3 完成摘要（2026-06-08）

**实现要点**（对应用户 Category 3 + 6）：
- **知识利用深化**：
  - 强化 `_ensure_prior_case_reasoning`：必须出现具体 `outcome=` + 借鉴语句。
  - prior_cases 已在 ReAct 阶段注入（含 match_score / outcome / related_rules），D3 使 PS 真正“用”起来。
- **执行反馈闭环**：
  - 新 `_format_execution_feedback` 从 `state["execution_results"]` 取最近 3 条。
  - 同时注入 ReAct Task 和 Structured Prompt 两个位置。
  - `_ensure_execution_learning` 后处理强制 reasoning 写明“参考过往执行结果调整”。
  - 效果：下一次 PS 运行时能看到上次 Execution 的 status/summary 并调整。
- **置信度 / 风险自评估**：
  - `_compute_confidence` 增加 `history_bonus`（正向历史案例加分）和 `exec_factor`（成功加 / 失败减），进入 min(LLM, computed) 安全路径。
  - `_enrich_solution_depth` 从失败历史案例和最近执行失败自动追加 `RiskItem`。
- **Prompt & 验证**：
  - 两个 prompt 模板增加 `{execution_feedback}` 区块 + 质量门禁。
  - 全量回归 250 passed；core capability eval offline gate 绿。

**未覆盖（留给后续）**：
- 显式 `confidence_rationale` 字段（可简单从 reasoning 派生）。
- 更强的向量相似度（当前仍为 keyword + graph + outcome 启发式）。
- Demo / Report 中展示“本次从执行历史学到了什么”。

D3 使 ProblemSolver 开始真正“会用经验” —— 历史案例不再是装饰，执行结果真正反哺下一轮推理。

## D4 完成摘要（2026-06-08 继续）

**实现要点**（对应用户 Category 4 + D4 计划）：
- **分类器返回置信度 + 不确定强制 mixed**：
  - `classify_problem` 现在返回 `(ProblemType, reason, confidence: float)`。
  - 当 max_score 低（<2）或 top 域间 margin 很小，自动返回 "mixed" + 较低 conf（~0.35-0.55）。这直接实现了“**不确定时走 mixed + 更多工具**”。
- **路由加宽（Orchestrator + Planner）**：
  - `resolve_context` 计算 `is_uncertain`，低 conf 时强制 is_security + is_operations 更宽，specialist_queue 包含更多专家。
  - `PipelinePlanner.build_specialist_queue` 也读取 conf 并 widen。
  - `OrchestrationContext` 新增 `classification_confidence` 和 `is_uncertain` 字段（向后兼容默认值）。
- **ProblemSolver 策略自适应**：
  - `_classify` / `run` 捕获 conf，传给 `_run_react` 和 `_synthesize_structured`。
  - 低 conf/mixed 时：priority_modules 强制为全量（mixed），ReAct/Structured prompt 末尾追加 adaptation_note，要求 self-critique。
  - 新 `_ensure_self_critique`（validate 阶段）：对低 conf 产出做后处理检查（root_causes 是否被 rec 方案缓解？cited rule_ids 是否出现在 rationale/impact？），缺口则在 reasoning 追加说明 + 补充 next_actions。
- **Prompt 强化**：结构化输出质量门禁增加 D4 self-critique 要求。
- **测试与门禁**：
  - `test_problem_classifier.py` 新增 `test_classify_uncertain_forces_mixed_low_conf`。
  - 所有 classify 调用站点已适配 3/4 返回值。
  - PS-CLS-01（12 条 golden）准确率继续满足 target（强信号案例不受弱信号逻辑影响）。
  - 相关测试 44 passed；core_capability eval offline gate 持续 [PASS]。
- **可观测**：分类日志现在包含 `conf=xx uncertain=yy`；OrchestrationContext 携带 conf 供下游使用。

**效果**：分类不再是“一次猜对就完”，而是带置信度的路由信号，能在模糊场景下主动拉宽专家队列、要求 PS 做更彻底的调查与自检，让路由和推理策略真正“因问题类型而异”。

**未覆盖（留给 D4 后续或 D5）**：
- 把 classification_confidence 持久化到 ProjectState / conversation_history / run report / demo 展示。
- 极低 conf 时的轻量 LLM 辅助重分类（当前仍纯启发式，保证离线确定性）。
- 统一 Agent 输出基类（AgentOutputBase）对齐。

D4 基本完成 Category 4 目标 + D4 计划中“分类策略自适应 + prompt 条件分支 + 轻量 self-critique”核心内容。
