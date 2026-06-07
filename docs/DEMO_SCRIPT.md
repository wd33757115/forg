# Forge Demo 讲稿（5 分钟版）

> 配合 `scripts/demo.ps1` 或 `run.bat` 使用。默认场景：**security**。

## 0. 开场（30 秒）

「Forge 是项目级 AI 操作系统：用户抛出一个等保/ITIL/技术问题，Supervisor 编排多 Agent 流水线，产出**可审计方案、合规结论、资料包与执行建议**。」

```powershell
.\scripts\demo.ps1 -Type security -AutoApprove -Report
# 或
.\run.bat --type security --auto-approve --no-feedback --report
```

---

## 第一步：判型与调查（60 秒）

**指着 ProblemSolver 面板讲：**

1. **问题类型** — `security` / `service_management` / `mixed`（CLI `--type` 可指定）
2. **Rule Pack 引用** — 至少 3 条真实 `rule_id`（如 `db-acs-001`）
3. **reasoning** — 分步推理，须含 rule_id 子串
4. **ReAct 日志**（可选展开 `-v`）— `prior_cases` 条数、工具调查清单

**金句：**「不是泛泛聊天，每条结论都挂在 Rule Pack 条款上。」

---

## 第二步：方案与 Handoff（60 秒）

**指着推荐方案 + Handoff 时间线：**

- 推荐方案 ID（如 `sol-a`）+ **decision_rationale**
- Handoff → Compliance：`rule_pack_references` + `root_causes`
- 若有 Security/Operations 专家：补充等保或 ITIL 视角

**金句：**「结构化上下文通过 handoff 传递，Compliance 不是重新猜方案。」

---

## 第三步：合规闭环（90 秒）

**指着 Compliance 面板：**

| 展示项 | 说明 |
|--------|------|
| `check_mode` | advisory（Demo 默认）/ strict / lenient |
| `matched_rules` | 即使 compliant 也展示通过项 |
| `failed_items` | strict 下更多；可触发重试（最多 2 次） |
| `handoff_rule_ids` | thinking 中可见 PS 传入的 rule_id |

**对比演示（可选）：**

```powershell
.\run.bat --type security --check-mode strict --auto-approve --no-feedback
.\run.bat --type security --check-mode lenient --auto-approve --no-feedback
```

**金句：**「同一项目证据，严格度可调；失败项带 rule_id 和 severity。」

---

## 第四步：半自治收尾（60 秒）

**指着置信度 → 审批 → 执行 → PM：**

1. **置信度** — ConfidenceScorer 因子树 → `auto_execute` / 需审批
2. **审批门控** — `--auto-approve` 或人工 `--approve` / `--reject`
3. **执行任务** — simulate / local_manifest / webhook（`.env` 配置）
4. **PM 顾问** — P0/P1 行动项与风险
5. **DocumentAgent** — 7 份资料（等保记录 + ITIL 事件/问题/变更）

**金句：**「从诊断到资料归档到执行清单，一条流水线讲完。」

---

## 三场景切换（附录）

| 命令 | 叙事重点 |
|------|----------|
| `--type security` | 等保 identity / 审计 / 边界 |
| `--type itil` | 事件分级、SLA、CAB 变更 |
| `--type mixed` | dengbao + itil 双轨 rule_id |

样例报告：`reports/sample_security.md`  
LLM 基线：`reports/llm_baseline/`

---

## 常见问题

- **无 API Key** → 启发式离线模式，引用率下降，适合测架构不适合对外 Demo
- **耗时** → 全链路 LLM 约 2–3 分钟/场景，提前 `--report` 保存
- **合规 non_compliant** → 看 `failed_items`，Supervisor 可重试 ProblemSolver
