# Forge 样例运行报告（等保 / 安全场景 · 脱敏）

> 来源：W1-2 LLM 全链路冒烟（`run_id` 已替换）。对外演示用，不含真实客户/项目标识。

| 字段 | 值 |
|------|-----|
| 项目 | `demo-security-001` |
| Run ID | `demo-run-001` |
| 场景 | 等保/安全 (security) |
| 耗时 | ~128s |
| 合规状态 | compliant |
| 置信度 | 1.0 |

## 问题输入

等保三级系统登录接口持续返回 401，审计日志显示认证失败激增。请对照 dengbao_2.0 身份鉴别控制项诊断根因，给出可执行处置方案并引用具体 rule_id。

## 决策链路

1. **问题类型** → `security`
2. **推荐方案** → `sol-a`（自评置信度 0.85）
3. **合规结论** → compliant（advisory）
4. **会话置信度** → 1.0 / auto_execute
5. **审批执行** → auto_approved

## ProblemSolver 方案

- **类型**: security
- **推荐方案**: `sol-a`

**现象**：登录接口持续返回 401，审计日志显示认证失败激增。  
**业务影响**：用户无法正常登录，业务操作中断。  
**等保维度**：对照 `db-acs-001` 身份鉴别、`db-aud-001` 安全审计。  
**ITIL 维度**：按 `itil-inc-001` 记录事件、`itil-prb-001` 启动问题管理。

### Rule Pack 引用（节选）

- `db-acs-001` 身份鉴别
- `db-app-001` 应用身份鉴别
- `db-aud-001` 安全审计
- `db-bnd-001` 边界防护
- `si-sec-001` 安全集成要求

### 决策依据

推荐 sol-a：优先恢复业务可用性，通过检查身份认证系统（`si-sec-001`）与密码策略（`db-acs-001`）快速满足等保要求，后续再执行长期加固方案。

## Compliance 检查结果

- **状态**: compliant | **模式**: advisory | **风险**: low
- **匹配规则**: `db-acs-001`, `db-aud-001`, `db-bnd-001`, `itil-inc-001`, `si-doc-001` 等
- **handoff_rule_ids**（thinking）: `db-acs-001`, `db-app-001`, `db-aud-001`, …

## 生成资料（7 份）

方案摘要、整改方案、整改记录、等保整改记录、ITIL 事件/问题记录、变更申请。

## PM 行动项（节选）

- [P0] 排查认证服务状态 — 运维工程师
- [P0] 分析防暴力破解锁定日志 — 安全管理员
- [P1] 提交变更审批 — 项目经理
- [P1] 短期加固密码策略 — 系统管理员

## 半自治收尾

- 置信度 **1.0** → `auto_execute`
- 执行任务 5 项（simulate 模式）
- 审批 **auto_approved**

---

完整技术报告见：`reports/llm_baseline/w1-2_security_run.md`  
Demo 讲稿见：`docs/DEMO_SCRIPT.md`
