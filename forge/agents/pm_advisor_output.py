"""Structured output models for PMAdvisorAgent."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RiskItem(BaseModel):
    """A risk surfaced for project-manager attention."""

    title: str
    severity: str = Field(description="low | medium | high | critical")
    impact: str = ""
    mitigation: str = ""


class ActionItem(BaseModel):
    """Prioritized action item for the project team."""

    id: str
    title: str
    priority: str = Field(description="P0 | P1 | P2 | P3")
    owner: str = Field(default="项目经理", description="Suggested owner role")
    deadline_hint: str = ""
    rationale: str = ""


class PMAdvisorOutput(BaseModel):
    """
    Project-manager advisory report synthesizing solution, compliance, and documents.

    Produced by PMAdvisorAgent after the specialist pipeline completes.
    """

    summary: str = Field(description="Executive summary for the project manager")
    situation_overview: str = Field(description="What happened and current status")
    key_findings: list[str] = Field(default_factory=list)
    risks: list[RiskItem] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    decision_points: list[str] = Field(
        default_factory=list,
        description="Decisions the PM should make or escalate",
    )
    report_outline: list[str] = Field(
        default_factory=list,
        description="Outline for stakeholder reporting deck or memo",
    )
    stakeholder_notes: str = Field(
        default="",
        description="Communication notes for leadership or customer",
    )

    def to_display_json(self) -> str:
        return self.model_dump_json(indent=2, ensure_ascii=False)
