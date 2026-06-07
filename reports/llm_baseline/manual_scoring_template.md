# W1-3 LLM 人工评分表（模板）

对 security / itil / mixed 三场景各填一份，保存为 `scoring_<scenario>.json`。

| 维度 | 1 | 2 | 3 | 4 | 5 | 得分 |
|------|---|---|---|---|---|------|
| Rule Pack 引用相关性 | | | | | | |
| reasoning 可解释性 | | | | | | |
| 方案可执行性 | | | | | | |
| 合规/ITIL 对齐 | | | | | | |

**均值目标**：≥3.5/5

## 运行 LLM 基线

```powershell
pytest tests/test_llm_reference_coverage.py -m llm -v
```
