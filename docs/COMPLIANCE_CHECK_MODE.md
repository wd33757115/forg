# Compliance check_mode 说明

Forge 支持三种合规检查严格度，通过 CLI `--check-mode` 或 `ProjectState.check_mode` 设置。

| 模式 | 行为 | 适用场景 |
|------|------|----------|
| **strict** | partial 可能升级为 non_compliant；合规因子 ×0.9 | 正式交付、审计前验收 |
| **advisory** | 默认；partial 可继续生成资料 | 日常诊断与 Demo |
| **lenient** | non_compliant 边界更宽松 | 探索性分析、早期方案 |

## check_mode 对 failed_items 的影响（实测参考）

以下数据来自 `tests/test_stage1_compliance_modes.py` 同款种子状态（`stage1-cmp`，含基础 WBS/文档证据）：

| check_mode | `failed_items` 纳入规则 | `compliance_status` | 说明 |
|------------|-------------------------|---------------------|------|
| **strict** | `fail` + `warning` 全部纳入 | 有 failed_items → **non_compliant** | 正式验收 / 审计 |
| **advisory** | 仅 `fail`（warning 仅在追溯中） | 低/中 severity → **partial**；高/关键 → non_compliant | Demo 默认 |
| **lenient** | 仅 `fail` 且 severity **high/critical** | 无阻断项 → compliant；否则 partial | 探索性分析 |

生成对比报告：`python scripts/compliance_mode_diff.py` → `reports/compliance_mode_diff.md`

**断言（自动化）**：`len(strict.failed_items) >= len(lenient.failed_items)`（见 `test_strict_has_more_failed_items_than_lenient`）。

**闭环内方案校验**（ProblemSolver handoff）：即使 `failed_items` 为空，报告仍输出 `matched_rules` 与 `check_explanations`（`forge/utils/report.py`）。Compliance thinking 的 `extra.handoff_rule_ids` 记录 PS 传入的 rule_id（见 `compliance.py` `run()`）。

## 合规重试（Supervisor）

在 `problem_compliance_loop` 工作流中：

1. ProblemSolver 产出方案 → Compliance 检查
2. 若 **non_compliant** 且 `compliance_retry_count < 2` → Supervisor 路由回 ProblemSolver 优化
3. 重试事件写入 `conversation_history`（`event=compliance_retry`）与 `pipeline_trace`
4. **strict** 模式下更易触发重试后的 block 建议（ConfidenceScorer 合规因子更低）

实现：`forge/utils/check_mode.py`、`forge/core/supervisor.py`（`MAX_COMPLIANCE_RETRIES = 2`）。
