# 路径 A：质量收口 + 能力深化（2 周任务表）

> **目标**：从「框架已齐」推进到 **v1.0 验收刻度** 可演示、可解释、可维护。  
> **原则**：先度量再改代码；LLM 路径与离线路径分开验收；不新增 v1.2 功能（向量检索 / Web UI / 真实 CMDB）。  
> **基线**：239+ offline tests（`-m "not llm"`）；参考 `STAGE1_SIGNOFF.md`（交付刻度）。  
> **核心能力签收**：以 [`CORE_CAPABILITY_SCORECARD.md`](CORE_CAPABILITY_SCORECARD.md) + `scripts/eval_core_capability.py` 为准。

---

## 验收刻度说明

| 符号 | 含义 |
|------|------|
| **P0** | 必须完成，否则不算路径 A 签收 |
| **P1** | 强烈建议，时间不够可延到第 3 周 |
| **DoD** | Definition of Done，可勾选验收 |

**路径 A 总签收条件（DoD）**

- [ ] 三场景 LLM 跑通，引用率 ≥70%，人工评分均值 ≥3.5/5
- [ ] 有一份对外可用的样例报告 `reports/sample_security.md`（脱敏）
- [ ] ProblemSolver 启发式兜底引用占比可度量，且有下降或说明
- [ ] Demo 固定叙事四步可在 5 分钟内讲清
- [ ] 212+ offline tests 仍绿；新增 LLM 回归纳入文档

---

## 第 1 周：ProblemSolver + LLM 度量（大脑优先）

### W1-D1～D2：建立 LLM 基线（只测不改）

| ID | 任务 | 操作 | DoD |
|----|------|------|-----|
| W1-1 | LLM 三场景基线 | `pytest tests/test_llm_reference_coverage.py -m llm -v` | 4/4 通过；记录耗时 |
| W1-2 | 全链路 LLM 冒烟 | `run.bat --type security --auto-approve --no-feedback`（有 Key） | 有 `last_solution`、合规、报告；截图或保存 state |
| W1-3 | 人工评分表 | 对 security / itil / mixed 各填 [评分表](#附录-a-llm-人工评分表) | 3 份 JSON 或 Markdown 记入 `reports/llm_baseline/` |
| W1-4 | 兜底引用占比 | 统计 `rule_pack_refs` 中来自 `ensure_minimum` 的比例（日志或一次性脚本） | 有数字：如「8 条中 3 条来自关键词兜底」 |

**本周止损**：若 LLM 测试大面积失败，先修 `llm_structured_mode` / API，不进入 Prompt 大改。

---

### W1-D3～D5：ProblemSolver 深度优化（P0）

| ID | 任务 | 文件 | 具体改动 | DoD |
|----|------|------|----------|-----|
| W1-5 | ReAct 强制 rule 清单 | `prompts/problem_solver/prompts.py` | REACT_TASK 末尾要求「无 rule_id 不得进入结构化」 | Prompt 评审通过 |
| W1-6 | 结构化质量门禁 | `agents/problem_solver.py` | `_validate_solution_output`：reasoning 须含 ≥1 个 `db-`/`itil-`/`si-` 子串 | 单测断言 |
| W1-7 | 减少空 reasoning | `problem_solver.py` | LLM 返回后若 reasoning 无 rule_id，从 refs 拼接一句 | 启发式 + LLM 路径测试 |
| W1-8 | 分类一致性 | `problem_classifier.py` + CLI | `--type` 与 `problem_type` 不一致时打 warning 日志 | 日志可见 |
| W1-9 | 知识注入可观测 | `problem_solver.py` | ReAct 前 log：`prior_cases` 条数 + 首条 id | pipeline_trace 或日志 |

**测试（P0）**

```powershell
pytest tests/test_problem_solver.py tests/test_prompts_abcd.py tests/test_llm_reference_coverage.py -m llm -v
pytest tests/ -q -m "not llm"
```

| DoD | 标准 |
|-----|------|
| 引用率 | LLM 三场景仍 ≥70% |
| reasoning | 3 场景中 ≥2 个 reasoning 含真实 rule_id 子串（人工或脚本） |

---

## 第 2 周：Compliance + Demo + 一致性

### W2-D1～D2：Compliance 可解释性（P0）

| ID | 任务 | 文件 | 具体改动 | DoD |
|----|------|------|----------|-----|
| W2-1 | check_mode 行为表 | `docs/COMPLIANCE_CHECK_MODE.md` | 补一张 strict/advisory/lenient 对 `failed_items` 数量示例 | 文档与 `test_stage1_compliance_modes` 一致 |
| W2-2 | 闭环校验上下文 | `compliance.py` | validate_solution 把 handoff 的 rule_ids 写入 thinking `extra` | compliance thinking 含 `handoff_rule_ids` |
| W2-3 | 报告合规节 | `utils/report.py` | 无 failed_items 时也输出 matched_rules 摘要 | 样例报告可读 |
| W2-4 | LLM Compliance（P1） | `compliance.py` | 闭环外全扫描可走 ReAct；闭环内保持 skip_react 求稳 | 文档说明策略 |

**DoD**：同一份 state 在 strict vs lenient 下 `len(failed_items)` 可复现差异（已有测试则勾选）。

---

### W2-D3～D4：Demo 叙事专业化（P0）

| ID | 任务 | 文件 | 具体改动 | DoD |
|----|------|------|----------|-----|
| W2-5 | 固定演示脚本 | `scripts/demo.ps1` 或 `docs/DEMO_SCRIPT.md` | 5 分钟讲稿：问题→方案→合规→置信/审批 | 新人可按稿操作 |
| W2-6 | 样例报告归档 | `reports/sample_security.md` | 从一次成功 LLM run 导出（脱敏） | 文件入库 |
| W2-7 | 故事板顺序 | `cli/demo_display.py` | 确认顺序：问题→PS→合规时间线→置信度→执行→PM | 与讲稿一致 |
| W2-8 | Handoff 可见 | `demo_display.py` | handoff 展示 rule_ids + decision_rationale | 目视检查 |

**Demo 四步叙事（背诵版）**

1. **判型与调查**：ProblemSolver 类型 + Rule Pack 引用 + reasoning  
2. **方案与 handoff**：推荐方案 id + 决策依据  
3. **合规闭环**：check_mode + failed_items + 重试（若有）  
4. **半自治**：置信度 → 审批 → 执行任务（或 blocked 说明）

---

### W2-D5：架构一致性收尾（P1）

| ID | 任务 | 文件 | 具体改动 | DoD |
|----|------|------|----------|-----|
| W2-9 | conversation 链 | 各 Agent `run()` | 凡连续 `record_*` 用 merged state（PS/Compliance 已修，抽查 SE/OP） | 无 handoff 被覆盖 |
| W2-10 | prompts 遗留 | `prompts/__init__.py` | 注明 legacy；新代码只走 loader | README 一句 |
| W2-11 | CODE_REVIEW 更新 | `docs/CODE_REVIEW.md` | 增「路径 A 签收」节 + 已知债 | 与本文交叉引用 |

---

## 每周检查点（Checkpoint）

| 时间 | 检查项 | 负责人 | 通过？ |
|------|--------|--------|--------|
| 周五 W1 | LLM 4/4 + 人工评分表完成 | | ☐ |
| 周五 W1 | offline 212+ 仍绿 | | ☐ |
| 周五 W2 | `sample_security.md` + Demo 讲稿 | | ☐ |
| 周五 W2 | 路径 A 总 DoD 全勾 | | ☐ |

---

## 不在路径 A 范围内（明确排除）

- 向量 / embedding 检索  
- Web 审批 UI、SSE  
- 真实 CMDB / ITSM webhook 生产对接  
- SkillRegistry 设计与实现  
- 新 Agent 或新 Rule Pack 域扩展  

---

## 命令速查

```powershell
# 离线回归（每日）
.\.venv\Scripts\python.exe -m pytest tests/ -q -m "not llm"

# LLM 引用率（每周至少 1 次，需 Key）
.\.venv\Scripts\python.exe -m pytest tests/test_llm_reference_coverage.py -m llm -v

# 全链路 Demo
.\run.bat --type security --auto-approve --no-feedback
.\run.bat --type mixed --check-mode advisory --report

# 保存样例报告（手动）
# 运行后选 Y 保存到 reports/，复制为 reports/sample_security.md
```

---

## 附录 A：LLM 人工评分表

每个场景（security / itil / mixed）填一行：

| 维度 | 1 | 3 | 5 | 得分 |
|------|---|---|---|------|
| 问题类型是否正确 | 错 | 基本对 | 完全对 | |
| Rule Pack 引用是否贴切 | 凑数 | 部分相关 | 高度相关 | |
| reasoning 是否可跟随 | 空洞 | 一般 | 清晰有 rule_id | |
| 方案是否可执行 | 泛泛 | 部分可执行 | 明确步骤与角色 | |
| 整体演示说服力 | 不能用 | 勉强 | 可对外讲 | |

**保存路径建议**：`reports/llm_baseline/YYYY-MM-DD_{scenario}.md`

---

## 附录 B：与 PHASED_ROADMAP 的关系

| 文档 | 刻度 |
|------|------|
| `PHASED_ROADMAP.md` | 交付刻度（模块有没有） |
| `PATH_A_QUALITY.md`（本文） | **验收刻度**（好不好用） |

路径 A 完成后，可将 `PHASED_ROADMAP.md` 中阶段 1 标注为：**交付 100% / 验收 90%+**，再启动 v1.2。

---

## 附录 C：路径 A 完成后 → v1.2 入口

1. Webhook Execution POC（单系统）  
2. embedding 检索（仅 ProblemSolver 注入）  
3. Web 只读 Run Report 查看器  
