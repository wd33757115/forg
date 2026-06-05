"""Structured output models for ProblemSolverAgent."""

from __future__ import annotations

from pydantic import BaseModel, Field

from forge.agents.output_base import AgentOutputBase


class RulePackReference(BaseModel):
    """Citation of a Rule Pack clause used in the solution."""

    rule_id: str
    module: str
    title: str
    relevance: str = Field(default="", description="Why this rule applies")


class SolutionOption(BaseModel):
    """A single remediation option with compliance and ITIL annotations."""

    id: str = Field(description="Unique solution identifier, e.g. sol-a")
    title: str
    description: str
    approach: str = Field(description="Technical or process approach summary")
    trade_offs: list[str] = Field(default_factory=list)
    compliance_impact: str = Field(
        default="",
        description="等保2.0 compliance impact and required evidence",
    )
    itil_guidance: str = Field(
        default="",
        description="Relevant ITIL/ISO20000 practice guidance",
    )
    estimated_effort: str = Field(default="medium", description="low | medium | high")
    risk_level: str = Field(default="medium", description="low | medium | high")


class SolutionOutput(AgentOutputBase):
    """
    Structured problem-solving result produced by ProblemSolverAgent.

    Serialized to JSON for downstream agents and human review.
    """

    problem_type: str = Field(
        default="technical",
        description="security | service_management | technical | mixed",
    )
    problem_analysis: str = Field(description="Structured analysis of the reported problem")
    root_causes: list[str] = Field(default_factory=list)
    rule_pack_references: list[RulePackReference] = Field(
        default_factory=list,
        description="Rule Pack clauses cited in the analysis",
    )
    solutions: list[SolutionOption] = Field(default_factory=list)
    recommended_solution_id: str = Field(
        description="ID of the recommended solution from the solutions list"
    )
    next_actions: list[str] = Field(
        default_factory=list,
        description="Concrete next steps for the project team",
    )
    dengbao_considerations: list[str] = Field(
        default_factory=list,
        description="等保2.0 specific considerations",
    )
    itil_considerations: list[str] = Field(
        default_factory=list,
        description="ITIL/ISO20000 process considerations",
    )