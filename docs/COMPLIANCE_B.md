# Compliance 深度优化（B 专项）签收说明

> 测试：`tests/test_compliance_b.py` · 模式对比：`scripts/compliance_mode_diff.py`

## 已实现

| ID | 能力 | 位置 |
|----|------|------|
| B1 | `check_explanations` / `failed_items` 含 `severity` + `suggestion` | `utils/compliance_explain.py` |
| B1 | severity 优先读 Rule Pack 定义 | `_rule_severity_index()` |
| B2 | strict / advisory / lenient 差异化 `failed_items` 过滤 | `_item_in_failed_set()` |
| B2 | `compliance_status` 与 failed_items 对齐 | `resolve_compliance_status_from_output()` |
| B3 | 三模式对比脚本 | `scripts/compliance_mode_diff.py` |
| 报告 | failed_items 展示 severity + 建议 | `utils/report.py`、`compliance.py` |

## 验收命令

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_compliance_b.py tests/test_stage1_compliance_modes.py -q
.\.venv\Scripts\python.exe scripts\compliance_mode_diff.py
```

## 观测字段

- `last_compliance_result.failed_items[].severity` / `.suggestion`
- `check_explanations[].severity` / `.suggestion`
- `failed_items_count`、`heuristic_compliance_status` vs `compliance_status`
