"""Structured output models for ProblemSolverAgent."""

from __future__ import annotations

from pydantic import BaseModel, Field


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


class SolutionOutput(BaseModel):
    """
    Structured problem-solving result produced by ProblemSolverAgent.

    Serialized to JSON for downstream agents and human review.
    """

    problem_analysis: str = Field(description="Structured analysis of the reported problem")
    root_causes: list[str] = Field(default_factory=list)
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

    def to_display_json(self) -> str:
        return self.model_dump_json(indent=2, ensure_ascii=False)
