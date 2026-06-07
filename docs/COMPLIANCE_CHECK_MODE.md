# Compliance check_mode 说明

Forge 支持三种合规检查严格度，通过 CLI `--check-mode` 或 `ProjectState.check_mode` 设置。

| 模式 | 行为 | 适用场景 |
|------|------|----------|
| **strict** | partial 可能升级为 non_compliant；合规因子 ×0.9 | 正式交付、审计前验收 |
| **advisory** | 默认；partial 可继续生成资料 | 日常诊断与 Demo |
| **lenient** | non_compliant 边界更宽松 | 探索性分析、早期方案 |

## 合规重试（Supervisor）

在 `problem_compliance_loop` 工作流中：

1. ProblemSolver 产出方案 → Compliance 检查
2. 若 **non_compliant** 且 `compliance_retry_count < 2` → Supervisor 路由回 ProblemSolver 优化
3. 重试事件写入 `conversation_history`（`event=compliance_retry`）与 `pipeline_trace`
4. **strict** 模式下更易触发重试后的 block 建议（ConfidenceScorer 合规因子更低）

实现：`forge/utils/check_mode.py`、`forge/core/supervisor.py`（`MAX_COMPLIANCE_RETRIES = 2`）。
