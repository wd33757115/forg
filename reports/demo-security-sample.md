# Forge 运行报告（样例）

| 字段 | 值 |
|------|-----|
| 项目 | cli-demo |
| 场景 | 等保 / security |
| 说明 | 归档样例 — 实际运行请使用 `.\run.bat --type security --report --no-feedback` |

## 问题

等保三级系统登录接口返回 401，需诊断根因并给出合规整改方案。

## 流水线（Rich Demo 故事板）

1. **用户问题** — 原始提问
2. **ProblemSolver 方案** — 分类、Rule Pack 引用、四段式分析
3. **Compliance** — 状态、风险、缺口；合规重试时间线
4. **Document** — 生成 Markdown 资料
5. **PM 顾问** — 行动项摘要
6. **执行任务** — 整改 WBS / 变更申请草稿（v1.1）
7. **审批流程** — 置信度门控；`--auto-approve` 或 `--approve`/`--reject`
8. **运行统计** — 耗时、Agent 调用、置信度分解

## 命令

```powershell
.\run.bat --type security --no-feedback
.\run.bat --type security --auto-approve --report --no-feedback
.\run.bat --plain --type security --no-feedback
```
