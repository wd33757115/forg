"""Compliance checking tools — base_si, dengbao_2.0, itil_iso20000."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from forge.core.rule_pack_loader import RulePackLoader
from forge.core.state import ProjectState

# ---------------------------------------------------------------------------
# 等保控制域检查项（按保护级别递增要求）
# ---------------------------------------------------------------------------
DENGBAO_CONTROL_CHECKS: dict[str, dict[str, Any]] = {
    "host_security": {
        "title": "安全计算环境（主机安全）",
        "categories": ["access_control", "audit"],
        "document_keywords": ["身份鉴别", "访问控制", "恶意代码", "主机安全", "安全计算"],
        "rule_ids": ["db-acs-001"],
        "min_level": "2",
    },
    "network_security": {
        "title": "安全通信网络 / 区域边界（网络安全）",
        "categories": ["network"],
        "document_keywords": ["边界", "防火墙", "网络", "区域边界"],
        "rule_ids": ["db-bnd-001"],
        "min_level": "2",
    },
    "audit": {
        "title": "安全审计",
        "categories": ["audit"],
        "document_keywords": ["安全审计", "日志", "审计"],
        "rule_ids": ["db-aud-001"],
        "min_level": "2",
    },
}

# ---------------------------------------------------------------------------
# ITIL 流程符合性检查项
# ---------------------------------------------------------------------------
ITIL_PROCESS_CHECKS: dict[str, dict[str, Any]] = {
    "incident": {
        "title": "事件管理",
        "document_keywords": ["事件", "incident", "故障记录"],
        "rule_ids": ["itil-inc-001"],
    },
    "change": {
        "title": "变更管理",
        "document_keywords": ["变更", "change"],
        "rule_ids": ["itil-chg-001"],
    },
    "configuration": {
        "title": "配置管理",
        "document_keywords": ["配置", "CMDB", "cmdb"],
        "rule_ids": ["itil-cfg-001"],
    },
    "problem": {
        "title": "问题管理",
        "document_keywords": ["问题", "根因", "problem", "rca"],
        "rule_ids": ["itil-prb-001"],
    },
}

# ---------------------------------------------------------------------------
# base_si 基础实施合规检查项
# ---------------------------------------------------------------------------
BASE_SI_CHECKS: dict[str, dict[str, Any]] = {
    "documentation": {
        "title": "资料完整性",
        "document_keywords": ["技术方案", "验收", "方案"],
        "wbs_required": [],
        "rule_ids": ["si-doc-001"],
    },
    "wbs_completeness": {
        "title": "WBS 完整性",
        "document_keywords": [],
        "wbs_required": ["requirements", "design", "implementation", "testing", "acceptance"],
        "rule_ids": ["si-wbs-001"],
    },
    "implementation_standards": {
        "title": "实施规范符合度",
        "document_keywords": ["接口", "变更", "联调"],
        "wbs_required": ["implementation"],
        "rule_ids": ["si-int-001"],
    },
}


def _primary_rule_id(*, rule_ids: list[str], check_id: str) -> str:
    """Pick canonical rule_id for a compliance check item."""
    if rule_ids:
        return rule_ids[0]
    if check_id.startswith(("db-", "itil-", "si-")):
        return check_id
    return ""


class DengbaoCheckInput(BaseModel):
    protection_level: str = Field(
        default="3",
        description="等保保护级别 1-5",
        pattern=r"^[1-5]$",
    )


def _doc_titles(state: ProjectState) -> set[str]:
    return {d.get("title", "").lower() for d in state.get("documents", [])}


def _doc_content_blob(state: ProjectState) -> str:
    parts = [d.get("title", "") for d in state.get("documents", [])]
    for entry in state.get("knowledge_base", []):
        parts.append(entry.get("content", ""))
    return " ".join(parts).lower()


def _has_document_evidence(titles: set[str], blob: str, keywords: list[str]) -> bool:
    for kw in keywords:
        kw_lower = kw.lower()
        if any(kw_lower in t for t in titles) or kw_lower in blob:
            return True
    return False


def _get_protection_level(state: ProjectState, override: str | None = None) -> str:
    if override:
        return override
    rule_pack = state.get("rule_pack") or {}
    return str(rule_pack.get("protection_level", "3"))


def check_base_compliance(state: ProjectState) -> dict[str, Any]:
    """
    Check base_si module: documentation completeness and implementation standards.

    Validates WBS coverage, core deliverables, and integration/change artifacts.
    """
    titles = _doc_titles(state)
    blob = _doc_content_blob(state)
    wbs = state.get("wbs", {})
    items: list[dict[str, Any]] = []

    for check_id, spec in BASE_SI_CHECKS.items():
        doc_ok = True
        wbs_ok = True
        missing: list[str] = []

        if spec["document_keywords"]:
            doc_ok = _has_document_evidence(titles, blob, spec["document_keywords"])
            if not doc_ok:
                missing.append(f"缺少文档: {', '.join(spec['document_keywords'])}")

        for wbs_item in spec["wbs_required"]:
            if wbs_item not in wbs:
                wbs_ok = False
                missing.append(f"WBS 缺失: {wbs_item}")

        status = "pass" if doc_ok and wbs_ok else "fail"
        rule_ids = spec.get("rule_ids", [])
        items.append(
            {
                "check_id": f"base_si-{check_id}",
                "title": spec["title"],
                "category": "base_si",
                "status": status,
                "detail": "符合要求" if status == "pass" else "; ".join(missing),
                "rule_id": _primary_rule_id(rule_ids=rule_ids, check_id=f"base_si-{check_id}"),
                "rule_reference": ", ".join(rule_ids) or "base_si Rule Pack",
            }
        )

    # Cross-check with Rule Pack rules
    loader = RulePackLoader.get_instance()
    base_mod = loader.load_default().get_module("base_si")
    if base_mod:
        for rule in base_mod.rules:
            for check in rule.checks:
                if check.startswith("document:"):
                    kw = check.replace("document:", "")
                    if not _has_document_evidence(titles, blob, [kw]):
                        items.append(
                            {
                                "check_id": rule.id,
                                "title": rule.title,
                                "category": rule.category,
                                "status": "fail",
                                "detail": f"Rule Pack 缺口: 缺少含 '{kw}' 的文档",
                                "rule_id": rule.id,
                                "rule_reference": ", ".join(rule.references),
                            }
                        )

    fail_count = sum(1 for i in items if i["status"] == "fail")
    score = max(0.0, 100.0 - fail_count * (100.0 / max(len(items), 1)))
    return {
        "module": "base_si",
        "module_name": "系统集成基础规范",
        "status": "pass" if fail_count == 0 else "gaps_found",
        "score": round(score, 1),
        "items": items,
        "summary": f"基础实施合规: {fail_count} 项未通过 / 共 {len(items)} 项",
    }


def check_dengbao_compliance(
    state: ProjectState,
    protection_level: str = "3",
) -> dict[str, Any]:
    """
    Check dengbao_2.0 module against protection level requirements.

    Implements host security, network security, and audit control checks.
    """
    level = int(protection_level)
    titles = _doc_titles(state)
    blob = _doc_content_blob(state)
    items: list[dict[str, Any]] = []

    for check_id, spec in DENGBAO_CONTROL_CHECKS.items():
        min_level = int(spec["min_level"])
        if level < min_level:
            items.append(
                {
                    "check_id": f"db-{check_id}",
                    "title": spec["title"],
                    "category": "dengbao_2.0",
                    "status": "pass",
                    "detail": f"保护级别 {level} 不要求此项",
                    "rule_id": _primary_rule_id(rule_ids=spec.get("rule_ids", []), check_id=f"db-{check_id}"),
                    "rule_reference": "N/A",
                }
            )
            continue

        has_evidence = _has_document_evidence(titles, blob, spec["document_keywords"])
        status = "pass" if has_evidence else "fail"
        detail = (
            "证据齐全"
            if has_evidence
            else f"等保{level}级要求: 缺少 {spec['title']} 相关证据材料"
        )
        items.append(
            {
                "check_id": f"db-{check_id}",
                "title": spec["title"],
                "category": "dengbao_2.0",
                "status": status,
                "detail": detail,
                "rule_id": _primary_rule_id(rule_ids=spec["rule_ids"], check_id=f"db-{check_id}"),
                "rule_reference": ", ".join(spec["rule_ids"]),
            }
        )

    # Rule Pack cross-check
    loader = RulePackLoader.get_instance()
    dengbao_mod = loader.load_default().get_module("dengbao_2.0")
    if dengbao_mod:
        for rule in dengbao_mod.rules:
            if rule.category in ("management",) and level >= 3:
                for check in rule.checks:
                    if check.startswith("document:"):
                        kw = check.replace("document:", "")
                        if not _has_document_evidence(titles, blob, [kw]):
                            items.append(
                                {
                                    "check_id": rule.id,
                                    "title": rule.title,
                                    "category": rule.category,
                                    "status": "fail",
                                    "detail": f"管理等保{level}级要求: 缺少 '{kw}' 文档",
                                    "rule_id": rule.id,
                                    "rule_reference": ", ".join(rule.references),
                                }
                            )

    fail_count = sum(1 for i in items if i["status"] == "fail")
    score = max(0.0, 100.0 - fail_count * (100.0 / max(len(items), 1)))
    return {
        "module": "dengbao_2.0",
        "module_name": f"网络安全等级保护 2.0（{level}级）",
        "status": "pass" if fail_count == 0 else "gaps_found",
        "score": round(score, 1),
        "items": items,
        "summary": f"等保{level}级合规: {fail_count} 项未通过 / 共 {len(items)} 项",
        "protection_level": str(level),
    }


def check_itil_compliance(state: ProjectState) -> dict[str, Any]:
    """
    Check itil_iso20000 module: incident, change, configuration, problem management.
    """
    titles = _doc_titles(state)
    blob = _doc_content_blob(state)
    items: list[dict[str, Any]] = []

    for check_id, spec in ITIL_PROCESS_CHECKS.items():
        has_evidence = _has_document_evidence(titles, blob, spec["document_keywords"])
        status = "pass" if has_evidence else "fail"
        items.append(
            {
                "check_id": f"itil-{check_id}",
                "title": spec["title"],
                "category": "itil_iso20000",
                "status": status,
                "detail": (
                    "流程证据齐全"
                    if has_evidence
                    else f"缺少 {spec['title']} 流程记录或文档"
                ),
                "rule_id": _primary_rule_id(rule_ids=spec["rule_ids"], check_id=f"itil-{check_id}"),
                "rule_reference": ", ".join(spec["rule_ids"]),
            }
        )

    loader = RulePackLoader.get_instance()
    itil_mod = loader.load_default().get_module("itil_iso20000")
    if itil_mod:
        for rule in itil_mod.rules:
            if rule.category == "service_level":
                for check in rule.checks:
                    if check.startswith("document:"):
                        kw = check.replace("document:", "")
                        if not _has_document_evidence(titles, blob, [kw]):
                            items.append(
                                {
                                    "check_id": rule.id,
                                    "title": rule.title,
                                    "category": rule.category,
                                    "status": "warning",
                                    "rule_id": rule.id,
                                    "detail": f"建议补充 SLA 文档: '{kw}'",
                                    "rule_reference": ", ".join(rule.references),
                                }
                            )

    fail_count = sum(1 for i in items if i["status"] == "fail")
    warn_count = sum(1 for i in items if i["status"] == "warning")
    score = max(0.0, 100.0 - fail_count * 20 - warn_count * 5)
    return {
        "module": "itil_iso20000",
        "module_name": "ITIL 4 + ISO/IEC 20000",
        "status": "pass" if fail_count == 0 else "gaps_found",
        "score": round(score, 1),
        "items": items,
        "summary": f"ITIL 流程合规: {fail_count} 项未通过, {warn_count} 项警告",
    }


def run_all_compliance_checks(
    state: ProjectState,
    *,
    protection_level: str | None = None,
    modules: list[str] | None = None,
) -> dict[str, Any]:
    """Run all enabled module checks and return raw results dict."""
    enabled = modules or state.get("enabled_modules") or [
        "base_si",
        "dengbao_2.0",
        "itil_iso20000",
    ]
    level = _get_protection_level(state, protection_level)
    results: dict[str, Any] = {"protection_level": level, "modules": {}}

    if "base_si" in enabled:
        results["modules"]["base_si"] = check_base_compliance(state)
    if "dengbao_2.0" in enabled:
        results["modules"]["dengbao_2.0"] = check_dengbao_compliance(state, level)
    if "itil_iso20000" in enabled:
        results["modules"]["itil_iso20000"] = check_itil_compliance(state)

    return results


def build_compliance_output_from_checks(
    raw: dict[str, Any],
    *,
    context: str = "",
    check_mode: str = "advisory",
) -> dict[str, Any]:
    """Assemble ComplianceOutput-compatible dict from raw check results."""
    from forge.utils.check_mode import compute_compliance_verdict

    module_results = list(raw.get("modules", {}).values())
    missing: list[str] = []
    recommendations: list[str] = []

    for mod in module_results:
        for item in mod.get("items", []):
            if item["status"] in ("fail", "warning"):
                missing.append(f"[{mod['module']}] {item['title']}: {item['detail']}")
                if item["status"] == "fail":
                    recommendations.append(
                        f"整改 {item['title']} — 参考 {item.get('rule_reference', 'Rule Pack')}"
                    )

    fail_total = sum(
        1
        for mod in module_results
        for item in mod.get("items", [])
        if item["status"] == "fail"
    )
    warn_total = sum(
        1
        for mod in module_results
        for item in mod.get("items", [])
        if item["status"] == "warning"
    )
    critical_fails = sum(
        1
        for mod in module_results
        for item in mod.get("items", [])
        if item["status"] == "fail" and "dengbao" in item.get("category", "")
    )

    mode = check_mode if check_mode in ("strict", "advisory", "lenient") else "advisory"
    overall_status, risk_level, compliance_status = compute_compliance_verdict(
        fail_total=fail_total,
        warn_total=warn_total,
        critical_fails=critical_fails,
        check_mode=mode,  # type: ignore[arg-type]
    )

    if context and "方案" in context:
        recommendations.append("对 ProblemSolver 推荐方案进行变更影响评估后再实施")

    next_action = (
        "立即组织等保与 ITIL 联合整改会议"
        if risk_level in ("critical", "high")
        else "按 recommendations 逐项补齐证据并更新合规台账"
    )

    return {
        "overall_status": overall_status,
        "risk_level": risk_level,
        "compliance_status": compliance_status,
        "protection_level": raw.get("protection_level"),
        "results": module_results,
        "missing_items": missing,
        "recommendations": recommendations,
        "next_action": next_action,
    }


def build_compliance_tools(state: ProjectState) -> list[BaseTool]:
    """Build LangChain tools bound to current project state."""

    def check_base() -> str:
        """Check base_si compliance: documentation completeness and implementation standards."""
        return json.dumps(check_base_compliance(state), ensure_ascii=False, indent=2)

    def check_dengbao(protection_level: str = "3") -> str:
        """Check dengbao_2.0 compliance for host/network/audit at given protection level (1-5)."""
        level = _get_protection_level(state, protection_level)
        return json.dumps(check_dengbao_compliance(state, level), ensure_ascii=False, indent=2)

    def check_itil() -> str:
        """Check itil_iso20000 compliance: incident, change, configuration, problem management."""
        return json.dumps(check_itil_compliance(state), ensure_ascii=False, indent=2)

    return [
        StructuredTool.from_function(
            func=check_base,
            name="check_base_compliance",
            description=check_base.__doc__ or "",
        ),
        StructuredTool.from_function(
            func=check_dengbao,
            name="check_dengbao_compliance",
            description=check_dengbao.__doc__ or "",
            args_schema=DengbaoCheckInput,
        ),
        StructuredTool.from_function(
            func=check_itil,
            name="check_itil_compliance",
            description=check_itil.__doc__ or "",
        ),
    ]


def run_compliance_research(state: ProjectState, context: str = "") -> str:
    """Execute all compliance tools programmatically (offline / pre-LLM research)."""
    raw = run_all_compliance_checks(state)
    sections = [
        ("base_si", json.dumps(raw["modules"].get("base_si", {}), ensure_ascii=False, indent=2)),
        (
            "dengbao_2.0",
            json.dumps(raw["modules"].get("dengbao_2.0", {}), ensure_ascii=False, indent=2),
        ),
        (
            "itil_iso20000",
            json.dumps(raw["modules"].get("itil_iso20000", {}), ensure_ascii=False, indent=2),
        ),
    ]
    body = "\n\n".join(f"### {name}\n{content}" for name, content in sections)
    if context:
        body = f"### Context\n{context}\n\n{body}"
    return body
