"""Document generation tools — build Markdown deliverables from solution + compliance."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from forge.agents.document_output import DocumentOutput, GeneratedDocument


def _now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _solution_rec(solution: dict[str, Any]) -> dict[str, Any]:
    rec_id = solution.get("recommended_solution_id", "")
    for sol in solution.get("solutions", []):
        if sol.get("id") == rec_id:
            return sol
    return solution.get("solutions", [{}])[0] if solution.get("solutions") else {}


def generate_remediation_plan(
    project_id: str,
    phase: str,
    solution: dict[str, Any],
    compliance: dict[str, Any],
) -> GeneratedDocument:
    """Generate 整改方案 / 技术方案 document."""
    rec = _solution_rec(solution)
    missing = compliance.get("missing_items", [])
    recs = compliance.get("recommendations", [])

    content = f"""# 整改方案 / 技术方案

| 字段 | 内容 |
|------|------|
| 项目 ID | {project_id} |
| 项目阶段 | {phase} |
| 方案 ID | {solution.get('recommended_solution_id', 'N/A')} |
| 编制时间 | {_now_str()} |
| 合规状态 | {compliance.get('compliance_status', 'unknown')} |

## 1. 问题分析

{solution.get('problem_analysis', '无')}

## 2. 根因分析

{chr(10).join(f'- {r}' for r in solution.get('root_causes', [])) or '- 待补充'}

## 3. 推荐方案

**{rec.get('title', '推荐方案')}**

{rec.get('description', '')}

### 实施路径

{rec.get('approach', '')}

### 等保影响

{rec.get('compliance_impact', solution.get('dengbao_considerations', [''])[0] if solution.get('dengbao_considerations') else '待评估')}

### ITIL 流程

{rec.get('itil_guidance', '')}

## 4. 合规缺口与整改映射

{chr(10).join(f'- {m}' for m in missing[:10]) or '- 无重大缺口'}

## 5. 整改建议

{chr(10).join(f'- {r}' for r in recs[:8]) or '- 按 Rule Pack 执行'}

## 6. 下一步行动

{chr(10).join(f'- {a}' for a in solution.get('next_actions', [])) or '- 按项目计划执行'}

## 7. 审批

| 角色 | 签字 | 日期 |
|------|------|------|
| 项目经理 | | |
| 安全负责人 | | |
| 技术负责人 | | |
"""
    return GeneratedDocument(
        doc_id=f"doc-{project_id}-remediation",
        doc_type="remediation_plan",
        title="整改方案 / 技术方案",
        content=content,
        metadata={"solution_id": solution.get("recommended_solution_id")},
    )


def generate_dengbao_record(
    project_id: str,
    solution: dict[str, Any],
    compliance: dict[str, Any],
) -> GeneratedDocument:
    """Generate 等保整改记录."""
    level = compliance.get("protection_level", "3")
    dengbao_results = next(
        (r for r in compliance.get("results", []) if r.get("module") == "dengbao_2.0"),
        {},
    )

    items_text = ""
    for item in dengbao_results.get("items", []):
        status_icon = "✓" if item.get("status") == "pass" else "✗"
        items_text += f"| {status_icon} | {item.get('title', '')} | {item.get('status', '')} | {item.get('detail', '')} |\n"

    content = f"""# 等级保护整改记录

| 字段 | 内容 |
|------|------|
| 项目 ID | {project_id} |
| 保护级别 | 等保 {level} 级 |
| 记录时间 | {_now_str()} |
| 合规状态 | {compliance.get('compliance_status', 'unknown')} |

## 1. 整改背景

{solution.get('problem_analysis', '')[:500]}

## 2. 等保控制项检查台账

| 状态 | 控制项 | 检查结果 | 说明 |
|------|--------|----------|------|
{items_text or '| - | - | - | 无数据 |'}

## 3. 等保考量

{chr(10).join(f'- {c}' for c in solution.get('dengbao_considerations', [])) or '- 见合规报告'}

## 4. 整改措施

{chr(10).join(f'- {r}' for r in compliance.get('recommendations', [])[:8]) or '- 按等保要求执行'}

## 5. 证据留存要求

- 身份鉴别与访问控制配置截图
- 安全审计日志样本（保留 ≥6 个月）
- 边界防护策略文档
- 安全管理制度更新记录

## 6. 复核签字

| 角色 | 签字 | 日期 |
|------|------|------|
| 等保专员 | | |
| 安全管理员 | | |
"""
    return GeneratedDocument(
        doc_id=f"doc-{project_id}-dengbao",
        doc_type="dengbao_record",
        title=f"等保{level}级整改记录",
        content=content,
        metadata={"protection_level": level},
    )


def generate_itil_incident_record(
    project_id: str,
    solution: dict[str, Any],
    compliance: dict[str, Any],
) -> GeneratedDocument:
    """Generate ITIL 事件记录."""
    content = f"""# ITIL 事件记录 (Incident Record)

| 字段 | 内容 |
|------|------|
| 事件单号 | INC-{project_id}-{datetime.now(timezone.utc).strftime('%Y%m%d')} |
| 项目 ID | {project_id} |
| 记录时间 | {_now_str()} |
| 优先级 | P2 |
| 状态 | 已分析 / 待实施 |

## 1. 事件描述

{solution.get('problem_analysis', '无描述')}

## 2. 影响范围

- 业务影响: 待评估
- 合规影响: {compliance.get('risk_level', 'unknown')} 风险

## 3. 处理过程

{chr(10).join(f'- {a}' for a in solution.get('next_actions', [])[:5]) or '- 按方案执行'}

## 4. 根因（初步）

{chr(10).join(f'- {r}' for r in solution.get('root_causes', [])) or '- 待问题管理流程确认'}

## 5. ITIL 流程对齐

{chr(10).join(f'- {c}' for c in solution.get('itil_considerations', [])) or '- Incident Management 标准流程'}

## 6. 关闭条件

- [ ] 服务恢复正常
- [ ] 用户确认
- [ ] 事件记录归档
"""
    return GeneratedDocument(
        doc_id=f"doc-{project_id}-itil-incident",
        doc_type="itil_incident",
        title="ITIL 事件记录",
        content=content,
    )


def generate_itil_problem_record(
    project_id: str,
    solution: dict[str, Any],
) -> GeneratedDocument:
    """Generate ITIL 问题记录."""
    content = f"""# ITIL 问题记录 (Problem Record)

| 字段 | 内容 |
|------|------|
| 问题单号 | PRB-{project_id}-{datetime.now(timezone.utc).strftime('%Y%m%d')} |
| 项目 ID | {project_id} |
| 记录时间 | {_now_str()} |
| 状态 | 根因分析中 |

## 1. 问题描述

{solution.get('problem_analysis', '')}

## 2. 根因分析 (RCA)

{chr(10).join(f'1. {r}' for r in solution.get('root_causes', [])) or '1. 待分析'}

## 3. 已知错误 / 临时措施

{_solution_rec(solution).get('description', '见推荐方案')}

## 4. 永久性修复方案

方案 ID: `{solution.get('recommended_solution_id', 'N/A')}`

{_solution_rec(solution).get('approach', '')}

## 5. 关联变更

见变更申请记录 CHG-{project_id}
"""
    return GeneratedDocument(
        doc_id=f"doc-{project_id}-itil-problem",
        doc_type="itil_problem",
        title="ITIL 问题记录",
        content=content,
    )


def generate_change_request(
    project_id: str,
    solution: dict[str, Any],
    compliance: dict[str, Any],
) -> GeneratedDocument:
    """Generate 变更申请记录."""
    rec = _solution_rec(solution)
    content = f"""# 变更申请记录 (Change Request)

| 字段 | 内容 |
|------|------|
| 变更单号 | CHG-{project_id}-{datetime.now(timezone.utc).strftime('%Y%m%d')} |
| 项目 ID | {project_id} |
| 申请时间 | {_now_str()} |
| 变更类型 | 标准变更 |
| 风险等级 | {rec.get('risk_level', 'medium')} |

## 1. 变更原因

{solution.get('problem_analysis', '')[:400]}

## 2. 变更内容

**{rec.get('title', '方案实施')}**

{rec.get('description', '')}

## 3. 实施方案

{rec.get('approach', '')}

## 4. 合规影响评估

- 合规状态: {compliance.get('compliance_status', 'unknown')}
- 等保影响: {rec.get('compliance_impact', '待评估')}
- 缺口项数: {len(compliance.get('missing_items', []))}

## 5. 回退方案

{chr(10).join(f'- {t}' for t in rec.get('trade_offs', [])) or '- 保留变更前配置快照，支持回滚'}

## 6. ITIL 变更管理

{rec.get('itil_guidance', '按 Change Enablement 流程执行')}

## 7. 审批

| 角色 | 意见 | 签字 | 日期 |
|------|------|------|------|
| 变更申请人 | | | |
| CAB | | | |
| 安全审核 | | | |
"""
    return GeneratedDocument(
        doc_id=f"doc-{project_id}-change",
        doc_type="change_request",
        title="变更申请记录",
        content=content,
        metadata={"solution_id": solution.get("recommended_solution_id")},
    )


def generate_document_bundle(
    project_id: str,
    phase: str,
    solution: dict[str, Any],
    compliance: dict[str, Any],
) -> DocumentOutput:
    """Generate the full document package from solution + compliance."""
    if not solution:
        return DocumentOutput(summary="无方案数据，跳过资料生成")

    docs = [
        generate_remediation_plan(project_id, phase, solution, compliance),
        generate_dengbao_record(project_id, solution, compliance),
        generate_itil_incident_record(project_id, solution, compliance),
        generate_itil_problem_record(project_id, solution),
        generate_change_request(project_id, solution, compliance),
    ]

    return DocumentOutput(
        documents=docs,
        summary=f"已生成 {len(docs)} 份资料：整改方案、等保记录、ITIL 事件/问题、变更申请",
        doc_types_generated=[d.doc_type for d in docs],
    )
