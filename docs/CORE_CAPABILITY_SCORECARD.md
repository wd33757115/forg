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

## 6. P0 编排改进（2026-06）

| 项 | 实现 |
|----|------|
| 结构化合规重试 | `state.compliance_feedback` + `utils/compliance_feedback.py` |
| PS Prompt 注入 | `compliance_feedback` 块于 ReAct / Structured |
| 置信度安全 | `min(LLM, computed)` + 启发式上限 `0.55` |
| 方案来源标识 | `SolutionOutput.solution_source` (`llm` \| `heuristic`) |

## 7. P1 编排收敛（2026-06 继续）

**P1-1: Specialist 队列三处定义收敛**

- 单一真相来源：`forge/core/orchestrator.py` 的 `specialists_for_type(problem_type, is_security, is_operations)`
- `PipelinePlanner.build_specialist_queue` 现在内部通过 `classify_problem` + `specialists_for_type` 计算（不再是纯关键词老逻辑）
- Supervisor 的主问题解决路径（PS entry + fallback）统一走 `Orchestrator` + `OrchestrationContext`
- 独立入口（standalone security/ops）仍保留显式硬编码队列（有意为之的“只跑这个专家”路径）

**P1-2: 合规闭环职责割裂**

- 新模块 `forge/core/compliance_loop.py`
  - 4 个谓词函数（`is_compliant` 等）+ `MAX_COMPLIANCE_RETRIES`
  - `ComplianceLoopController` 类：
    - `decide_after_compliance(state) -> SupervisorDecision`
    - `build_retry_updates(...)`（含结构化 feedback）
    - 内部 `_build_retry_feedback_message`
- Supervisor 注入 `self._compliance_loop = ComplianceLoopController()`
- `decide_after_compliance` 和重试状态准备委托给 controller
- 向后兼容：`from forge.core.supervisor import is_compliant, should_generate_documents, ...` 仍可用（re-export）

## 9. D3 深度（2026-06 继续，ProblemSolver 知识+闭环）

## 10. D4 分类与自适应路由（2026-06-08）

- classify_problem 升级为返回 confidence；不确定（低分/小 margin）自动 → mixed + 低 conf。
- Orchestrator / PipelinePlanner 据 conf 自动加宽 specialist_queue（更多 Security + Operations）。
- PS 接收 conf 后自适应：低 conf/mixed 时强制全模块 + 历史案例 + 注入 self-critique 要求；validate 阶段 _ensure_self_critique 做后处理缺口检测与 next_actions 补强。
- PS-CLS-01 准确率门禁不受影响（golden 案例信号强）；新增 uncertain case 覆盖测试。
- 验证：全量测试绿；offline KPI gate PASS。

（继续保持与 P0/P1 可靠性不冲突原则。）

## 11. 记忆与持久化（2026-06 pivot 开始，遗留大项）

- 设计参考 Grok 风格：结构化（case/outcome/rule-linked）、分层（working + episodic + semantic + procedural）、写回（execution/compliance/finalize 结果持久化）、项目级跨会话。
- M0 实现：
  - `forge/core/memory/manager.py` + `ProjectMemory`（facade、append_case/execution_outcome、search_similar、to_patch）。
  - `state_persistence.py` 不再重置 memory_graph；prepare 时 _ensure_durable_memory（kb 存在即重建/保留）。
  - `knowledge_extract.py`（finalize）现在通过 manager 写入 durable execution outcomes，使 D3 执行反馈闭环真正跨 run 有效。
  - `core/memory/__init__.py` 轻量（仅 graph 模型，避免循环）。
- 验证：test_state_persistence 新增 durable graph + manager 检索用例通过；PS + knowledge_memory 25 passed；core_capability offline gate 持续 [PASS]；-k "not llm" 整体绿。
- 文档：新增 `MEMORY_PERSISTENCE_DESIGN.md`（完整架构、Grok 映射、路线图）。
- 影响：ProblemSolver 的“会用经验”现在有持久化后盾；其他 Agent（Compliance、PM）未来可直接复用 manager 检索历史模式/风险。

后续 M1：episodic 记录、更多写点、CLI 增强、backend 抽象。

- 执行反馈闭环：`state.execution_results` → `_format_execution_feedback` → 注入 PS ReAct/Structured Prompt；`_ensure_execution_learning` 强制 reasoning 引用执行结果并调整。
- 知识利用：prior_cases（含 outcome/match）强制进入 reasoning（_ensure_prior_case_reasoning 强化）；历史失败案例自动补充结构化 risks。
- 置信度自评估：`_compute_confidence` 加入 history_bonus + exec_factor（成功正向、失败负向），进入 min(LLM, computed) 路径。
- 风险自评估：从 prior failed cases + recent exec failures 自动生成 RiskItem。
- 验证：全量 250 passed；core_capability offline gate 持续绿。

---

## 8. 当前基线（签收后更新）

运行 `eval_core_capability.py` 后在此记录：

- Offline：**以 `latest.json` 的 `offline_pass` 为准**
- 测试：`pytest -m "not llm"` 全绿
- LLM：`pytest -m llm` 按需
