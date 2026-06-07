# Demo C 专项 — CLI 思考链路可视化

> **目标**：Demo 与运行报告以「决策摘要 + 四步叙事」呈现，完整追踪按需展开。  
> **关联**：[DEMO_SCRIPT.md](DEMO_SCRIPT.md) · [COMPLIANCE_B.md](COMPLIANCE_B.md)

---

## C1 — Rich Demo 四步叙事

`forge/cli/demo_display.py` 中 `ForgeDemoDisplay.print_demo_result()` 固定输出顺序：

| 区块 | 内容 |
|------|------|
| **决策摘要（5 步）** | 判型 → 方案 → 合规 → 半自治 → 交付 |
| **① 判型与调查** | ProblemSolver 方案 + Security/Operations 专家补充 |
| **② 方案与 Handoff** | Agent 间 handoff 链（rule_ids / rationale） |
| **③ 合规闭环** | Compliance 详情 + 合规时间线（含重试） |
| **④ 半自治收尾** | 置信度分解 → 审批门控 → 执行 → PM → Document |

## C2 — 运行报告

- 报告在「问题输入」后插入 `## 决策摘要`（`forge/utils/decision_summary.py`）。
- 原「决策链路」五 bullet 已合并进决策摘要。
- `pipeline_trace`、思考链路、Handoff 移至 **`## 附录：完整追踪`**。

## C3 — Verbose 与追踪导出

```powershell
# DEBUG 日志 + Demo 展开 pipeline / thinking / 统计
py main.py "等保三级登录401" -v

# 导出 JSON（默认 reports/trace_<run_id>.json）
py main.py "等保三级登录401" --export-trace
py main.py "等保三级登录401" --export-trace reports/my_trace.json
```

`--export-trace` 写入字段：`pipeline_trace`、`conversation_history`、`agent_errors`、`reference_provenance`、`classification_conflict` 等（见 `forge/utils/trace_export.py`）。

## 验收

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_demo_display_c.py tests/test_report.py -q
```

- [ ] Rich Demo 顶部可见 5 条决策摘要
- [ ] 四步标题与 DEMO_SCRIPT 一致
- [ ] `-v` 在 Demo 末尾展开完整追踪
- [ ] `--export-trace` 生成可解析 JSON
- [ ] Markdown 报告含决策摘要 + 附录追踪
