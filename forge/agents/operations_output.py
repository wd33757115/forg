"""Structured output models for OperationsAgent (ITIL/ISO20000 focus)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from forge.agents.output_base import AgentOutputBase


class IncidentGuidance(BaseModel):
    """ITIL incident management guidance."""

    summary: str = ""
    priority: str = Field(default="P3", description="P1 | P2 | P3 | P4")
    impact: str = ""
    response_steps: list[str] = Field(default_factory=list)


class ChangeGuidance(BaseModel):
    """ITIL change enablement recommendation."""

    change_type: str = Field(default="normal", description="standard | normal | emergency")
    title: str
    risk_level: str = Field(description="low | medium | high")
    approval_path: list[str] = Field(default_factory=list)
    rollback_plan: str = ""


class OperationsOutput(AgentOutputBase):
    """
    Structured ITIL/ISO20000 service management advisory report.

    Covers incident, problem, change, and knowledge management guidance.
    """

    practice_area: str = Field(
        description="incident | problem | change | knowledge | mixed",
    )
    situation_summary: str = ""
    incident_guidance: IncidentGuidance | None = None
    root_cause_analysis: list[str] = Field(default_factory=list)
    change_recommendations: list[ChangeGuidance] = Field(default_factory=list)
    knowledge_base_entries: list[str] = Field(
        default_factory=list,
        description="Suggested KB articles or known-error records",
    )
    sla_considerations: str = ""
    itil_rule_references: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)