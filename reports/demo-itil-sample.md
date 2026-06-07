# Forge 运行报告（样例）— ITIL 场景

| 字段 | 值 |
|------|-----|
| 场景 | ITIL / operations |
| 说明 | 事件与问题管理类提问演示 |

## 命令

```powershell
.\run.bat --type itil --no-feedback
.\run.bat --type mixed --auto-approve --no-feedback
```

## 预期输出要点

- OperationsAgent ITIL 实践域分析
- Compliance `check_mode` 三种模式：`--check-mode strict|advisory|lenient`
- Handoff 链：ProblemSolver → Compliance → Document → PM → Execution → Approval
