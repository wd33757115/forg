"""Diagnostic tools for ProblemSolverAgent."""

from __future__ import annotations

from pydantic import BaseModel, Field

from forge.core.rule_pack import RuleModule


class DiagnosisResult(BaseModel):
    summary: str
    actions: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


_SYMPTOM_PATTERNS: list[tuple[list[str], str, list[str], list[str]]] = [
    (
        ["超时", "timeout", "慢", "latency"],
        "Performance degradation detected — likely network, database, or resource contention.",
        [
            "Collect latency metrics at each integration hop",
            "Review recent configuration changes in change log",
            "Check ITIL capacity management thresholds",
        ],
        ["performance", "integration"],
    ),
    (
        ["登录", "认证", "auth", "401", "403"],
        "Authentication/authorization failure — check identity integration and policy sync.",
        [
            "Verify SSO/LDAP connectivity and certificate validity",
            "Audit role mappings against 等保 access control requirements",
            "Review recent permission change requests",
        ],
        ["security", "access_control"],
    ),
    (
        ["接口", "api", "integration", "对接"],
        "Integration interface issue — validate contract, data mapping, and error handling.",
        [
            "Compare API schema against integration design document",
            "Enable structured logging on both endpoints",
            "Schedule joint troubleshooting session with vendor",
        ],
        ["integration", "api"],
    ),
]


def analyze_symptoms(text: str, packs: dict[str, RuleModule]) -> DiagnosisResult:
    """Rule-based symptom analysis (Phase 1). LLM replaces this in Phase 2."""
    lowered = text.lower()

    for keywords, summary, actions, tags in _SYMPTOM_PATTERNS:
        if any(kw in lowered for kw in keywords):
            # Enrich with applicable Rule Pack references
            extra: list[str] = []
            for pack in packs.values():
                for rule in pack.rules:
                    if any(t in rule.category for t in tags):
                        extra.append(f"Reference: [{pack.module_id}] {rule.id} — {rule.title}")
            return DiagnosisResult(
                summary=summary,
                actions=actions + extra[:2],
                tags=tags,
            )

    return DiagnosisResult(
        summary="Insufficient symptom data — gather logs, timeline, and affected WBS items.",
        actions=[
            "Document incident timeline and blast radius",
            "Assign owner per ITIL incident management",
            "Escalate to ProblemSolver with structured evidence",
        ],
        tags=["unknown"],
    )
