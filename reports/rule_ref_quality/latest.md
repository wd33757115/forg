# Rule Pack Reference Quality Report (D2)

生成时间: 2026-06-07T16:06:15.877367+00:00

## security
| rule_id | sev | rel_score | causal | cause? | source | title |
|---------|-----|-----------|--------|--------|--------|-------|
| `db-bnd-001` | critical | 0.88 | 0.5 | N | research | 边界防护 |
| `db-net-002` | high | 0.88 | 0.5 | N | research | 入侵防范 |
| `db-acs-002` | critical | 0.72 | 0.5 | N | scored | 访问控制 |
| `si-ms-001` | high | 0.72 | 0.5 | N | scored | 项目启动里程碑 |
| `si-sec-001` | high | 0.72 | 0.5 | N | scored | 安全集成要求 |
| `si-wbs-001` | high | 0.72 | 0.5 | N | scored | WBS完整性 |
| `db-acs-001` | critical | 0.72 | 0.35 | N | keyword | 身份鉴别 |
| `db-aud-001` | high | 0.66 | 0.35 | N | keyword | 安全审计 |

## itil
| rule_id | sev | rel_score | causal | cause? | source | title |
|---------|-----|-----------|--------|--------|--------|-------|
| `itil-cfg-001` | medium | 0.88 | 0.5 | N | research | 配置管理 |
| `itil-chg-002` | high | 0.88 | 0.5 | N | research | CAB 变更评审 |
| `itil-inc-002` | critical | 0.88 | 0.5 | N | research | 重大事件升级 |
| `itil-prb-001` | medium | 0.88 | 0.5 | N | research | 问题管理 |
| `itil-prb-002` | medium | 0.88 | 0.5 | N | research | 已知错误管理 |
| `itil-chg-001` | high | 0.66 | 0.35 | N | keyword | 变更管理 |
| `itil-inc-001` | high | 0.66 | 0.35 | N | keyword | 事件管理 |
| `itil-slm-001` | medium | 0.66 | 0.35 | N | keyword | 服务级别管理 |

## mixed
| rule_id | sev | rel_score | causal | cause? | source | title |
|---------|-----|-----------|--------|--------|--------|-------|
| `db-acs-002` | critical | 0.88 | 0.5 | N | research | 访问控制 |
| `db-aud-001` | high | 0.88 | 0.5 | N | research | 安全审计 |
| `db-net-002` | high | 0.88 | 0.5 | N | research | 入侵防范 |
| `db-net-003` | high | 0.88 | 0.5 | N | research | 恶意代码防范（网络） |
| `si-sec-001` | high | 0.72 | 0.5 | N | scored | 安全集成要求 |
| `db-acs-001` | critical | 0.66 | 0.35 | N | keyword | 身份鉴别 |
| `db-bnd-001` | critical | 0.66 | 0.35 | N | keyword | 边界防护 |
| `itil-inc-001` | high | 0.66 | 0.35 | N | keyword | 事件管理 |

