"""Pre-seed minimal project evidence for repeatable demo runs."""

from __future__ import annotations

from forge.core.rule_pack_loader import RulePackLoader
from forge.core.state import ProjectState

_DEMO_DOCUMENTS: list[dict[str, str]] = [
    {"title": "技术方案", "doc_type": "方案", "content": "系统集成技术方案（演示预置）"},
    {"title": "接口设计文档", "doc_type": "接口", "content": "接口与联调规范（演示预置）"},
    {"title": "验收测试报告", "doc_type": "验收", "content": "UAT 验收记录（演示预置）"},
    {"title": "身份鉴别与访问控制说明", "doc_type": "等保", "content": "身份鉴别、访问控制措施"},
    {"title": "安全审计与日志管理", "doc_type": "等保", "content": "安全审计、日志留存策略"},
    {"title": "边界防护与网络安全", "doc_type": "等保", "content": "区域边界与防火墙策略"},
    {"title": "事件管理流程", "doc_type": "流程", "content": "ITIL 事件记录与响应流程"},
    {"title": "变更管理流程", "doc_type": "流程", "content": "变更申请与 CAB 评审流程"},
    {"title": "配置管理 CMDB 基线", "doc_type": "配置", "content": "配置项与 CMDB 基线说明"},
    {"title": "问题管理与根因分析", "doc_type": "流程", "content": "问题单与 RCA 记录"},
    {"title": "SLA 服务级别协议", "doc_type": "SLA", "content": "服务级别与响应时间约定"},
]

_DEMO_WBS: dict[str, dict[str, str]] = {
    "requirements": {"name": "需求分析"},
    "design": {"name": "设计"},
    "implementation": {"name": "实施"},
    "testing": {"name": "测试"},
    "acceptance": {"name": "验收"},
}


def _rule_pack_document_keywords() -> list[str]:
    """Collect document: check keywords from all Rule Pack modules."""
    loader = RulePackLoader.get_instance()
    pack = loader.load_default()
    keywords: list[str] = []
    seen: set[str] = set()
    for module_name in ("base_si", "dengbao_2.0", "itil_iso20000"):
        mod = pack.get_module(module_name)
        if not mod:
            continue
        for rule in mod.rules:
            for check in rule.checks:
                if check.startswith("document:"):
                    kw = check.replace("document:", "").strip()
                    if kw and kw not in seen:
                        seen.add(kw)
                        keywords.append(kw)
    return keywords


def apply_demo_evidence_seed(state: ProjectState) -> ProjectState:
    """
    Add minimal documents/WBS when the project has no evidence yet.

    Helps preset demo scenarios reach partial/compliant and generate Document bundle
    under advisory check_mode without masking real project data on resume.
    """
    if state.get("documents"):
        return state
    state = dict(state)
    state["documents"] = [dict(doc) for doc in _DEMO_DOCUMENTS]
    wbs = dict(state.get("wbs") or {})
    for key, node in _DEMO_WBS.items():
        wbs.setdefault(key, node)
    state["wbs"] = wbs

    rp_keywords = _rule_pack_document_keywords()
    kb = list(state.get("knowledge_base") or [])
    kb.append(
        {
            "id": "kb-demo-evidence-index",
            "category": "demo_evidence",
            "content": " ".join(rp_keywords),
            "source": "demo_seed",
            "tags": ["demo", "compliance_evidence"],
            "metadata": {"keyword_count": len(rp_keywords)},
        }
    )
    state["knowledge_base"] = kb
    return state
