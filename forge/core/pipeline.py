"""Structured pipeline planning for the Forge Supervisor."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from forge.agents.problem_classifier import classify_problem
from forge.core.state import (
    WORKFLOW_OPERATIONS_STANDALONE,
    WORKFLOW_PROBLEM_COMPLIANCE_LOOP,
    WORKFLOW_SECURITY_STANDALONE,
)


# Canonical ordered stages in the standard problem-solving pipeline
STAGE_PROBLEM_SOLVER = "problem_solver"
STAGE_SECURITY = "security"
STAGE_OPERATIONS = "operations"
STAGE_COMPLIANCE = "compliance"
STAGE_DOCUMENT = "document"
STAGE_PM_ADVISOR = "pm_advisor"
STAGE_FINALIZE = "finalize"


@dataclass
class PipelinePlan:
    """Human-readable execution plan attached to ProjectState."""

    workflow: str
    stages: list[str] = field(default_factory=list)
    specialist_queue: list[str] = field(default_factory=list)
    scenario: str = "general"

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow": self.workflow,
            "stages": self.stages,
            "specialist_queue": self.specialist_queue,
            "scenario": self.scenario,
        }

    def describe(self) -> str:
        return " → ".join(self.stages)


class PipelinePlanner:
    """Build deterministic pipeline plans from user intent keywords."""

    def detect_scenario(self, content: str, *, is_security: bool, is_operations: bool, is_problem: bool) -> str:
        if is_security and is_operations:
            return "mixed"
        if is_security and is_problem:
            return "security"
        if is_operations and is_problem:
            return "operations"
        if is_security:
            return "security_audit"
        if is_operations:
            return "operations_audit"
        if is_problem:
            return "general"
        return "unknown"

    def build_specialist_queue(self, content: str, *, is_security: bool, is_operations: bool) -> list[str]:
        """
        Compute specialist queue using the single source of truth (P1).

        Delegates (lazily) to orchestrator.specialists_for_type after classifying problem_type.
        D4: also considers classification confidence — low conf forces wider queue (mixed-like).
        """
        from forge.core.orchestrator import specialists_for_type

        ptype, _, conf = classify_problem(content)
        # Widen for uncertain classification (D4)
        widen = conf < 0.55 or ptype == "mixed"
        sec = is_security or widen
        ops = is_operations or (widen and ptype in ("mixed", "service_management"))
        return specialists_for_type(ptype, is_security=sec, is_operations=ops)

    def build_for_problem_loop(
        self,
        content: str,
        *,
        is_security: bool,
        is_operations: bool,
    ) -> PipelinePlan:
        specialists = self.build_specialist_queue(
            content, is_security=is_security, is_operations=is_operations
        )
        stages = [STAGE_PROBLEM_SOLVER, *specialists, STAGE_COMPLIANCE, STAGE_DOCUMENT, STAGE_PM_ADVISOR]
        return PipelinePlan(
            workflow=WORKFLOW_PROBLEM_COMPLIANCE_LOOP,
            stages=stages,
            specialist_queue=specialists,
            scenario=self.detect_scenario(
                content,
                is_security=is_security,
                is_operations=is_operations,
                is_problem=True,
            ),
        )

    def build_for_security_standalone(self, content: str) -> PipelinePlan:
        return PipelinePlan(
            workflow=WORKFLOW_SECURITY_STANDALONE,
            stages=[STAGE_SECURITY, STAGE_COMPLIANCE, STAGE_PM_ADVISOR],
            specialist_queue=[STAGE_SECURITY],
            scenario="security_audit",
        )

    def build_for_operations_standalone(self, content: str) -> PipelinePlan:
        return PipelinePlan(
            workflow=WORKFLOW_OPERATIONS_STANDALONE,
            stages=[STAGE_OPERATIONS, STAGE_PM_ADVISOR],
            specialist_queue=[STAGE_OPERATIONS],
            scenario="operations_audit",
        )

    def build_for_compliance_standalone(self) -> PipelinePlan:
        return PipelinePlan(
            workflow="compliance_standalone",
            stages=[STAGE_COMPLIANCE, STAGE_PM_ADVISOR],
            specialist_queue=[],
            scenario="compliance_audit",
        )

    def build_for_document_standalone(self) -> PipelinePlan:
        return PipelinePlan(
            workflow="document_standalone",
            stages=[STAGE_DOCUMENT, STAGE_PM_ADVISOR],
            specialist_queue=[],
            scenario="document",
        )
