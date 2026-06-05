"""Structured output models for ComplianceAgent."""

from __future__ import annotations

from pydantic import BaseModel, Field

from forge.agents.output_base import AgentOutputBase


class CheckItem(BaseModel):
    """A single compliance check item within a module."""

    check_id: str
    title: str
    category: str
    status: str = Field(description="pass | fail | warning")
    detail: str = ""
    rule_reference: str = ""


class ModuleComplianceResult(BaseModel):
    """Compliance result for one standard module."""

    module: str = Field(description="base_si | dengbao_2.0 | itil_iso20000")
    module_name: str = ""
    status: str = Field(description="pass | gaps_found | not_applicable")
    score: float = Field(ge=0.0, le=100.0, description="Compliance score 0-100")
    items: list[CheckItem] = Field(default_factory=list)
    summary: str = ""


class ComplianceOutput(AgentOutputBase):
    """
    Structured multi-standard compliance report.

    Produced by ComplianceAgent after running base_si, dengbao_2.0, and
    itil_iso20000 checks against project artifacts and process evidence.
    """

    overall_status: str = Field(
        description="pass | gaps_found | critical",
    )
    risk_level: str = Field(
        description="low | medium | high | critical",
    )
    protection_level: str | None = Field(
        default=None,
        description="等保 protection level used for dengbao_2.0 checks (1-5)",
    )
    results: list[ModuleComplianceResult] = Field(default_factory=list)
    missing_items: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    next_action: str = ""