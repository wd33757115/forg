"""Document generation tools for DocumentAgent."""

from __future__ import annotations

from pydantic import BaseModel, Field

from forge.core.state import ProjectState


class DocumentOutline(BaseModel):
    title: str
    doc_type: str
    sections: list[str] = Field(default_factory=list)


_TEMPLATES: dict[str, tuple[str, list[str]]] = {
    "方案": (
        "技术实施方案",
        [
            "项目概述与目标",
            "现状分析与需求",
            "总体架构设计",
            "详细实施方案",
            "安全与等保合规设计",
            "实施计划与里程碑",
            "风险与应对措施",
            "验收标准",
        ],
    ),
    "报告": (
        "项目阶段报告",
        [
            "本期工作完成情况",
            "WBS进度与偏差分析",
            "问题与风险台账",
            "合规检查摘要",
            "下期工作计划",
        ],
    ),
    "等保": (
        "等级保护合规材料",
        [
            "定级与备案信息",
            "安全物理环境",
            "安全通信网络",
            "安全区域边界",
            "安全计算环境",
            "安全管理中心",
            "安全管理制度",
            "安全管理机构",
            "安全管理人员",
            "安全建设管理",
            "安全运维管理",
        ],
    ),
}


def generate_document_outline(request: str, state: ProjectState) -> DocumentOutline:
    """Produce a document outline based on request keywords (Phase 1 heuristic)."""
    lowered = request.lower()

    for keyword, (title, sections) in _TEMPLATES.items():
        if keyword in lowered or keyword in request:
            return DocumentOutline(title=title, doc_type=keyword, sections=sections)

    # Default: generic deliverable
    phase = state.get("current_phase", "execution")
    return DocumentOutline(
        title=f"{phase} 阶段交付物",
        doc_type="general",
        sections=[
            "背景与范围",
            "执行记录",
            "结果与证据",
            "合规引用",
            "审批与签收",
        ],
    )
