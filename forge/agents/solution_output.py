"""Structured output models for ProblemSolverAgent."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from forge.agents.output_base import AgentOutputBase


class RulePackReference(BaseModel):
    """Citation of a Rule Pack clause used in the solution."""

    rule_id: str
    module: str
    title: str
    relevance: str = Field(default="", description="Why this rule applies")
    reference_source: str = Field(
        default="",
        description="Provenance: keyword | scored | minimum_pad | research | llm",
    )
    relevance_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Heuristic pertinence to the problem (higher = more specific)",
    )
    causal_quality: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="How well the relevance explains a causal link from phenomenon to this rule (D2)",
    )


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


class RiskItem(BaseModel):
    """A residual risk associated with the recommended (or considered) solution."""

    title: str
    severity: str = Field(default="medium", description="low | medium | high | critical")
    likelihood: str = Field(default="medium", description="low | medium | high")
    mitigation: str = Field(default="")
    related_rule_ids: list[str] = Field(default_factory=list)


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
    decision_rationale: str = Field(
        default="",
        description="Why the recommended solution was chosen (explainability)",
    )
    reasoning: str = Field(
        default="",
        description="Detailed reasoning chain: classification → evidence → options → recommendation",
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Self-assessed confidence in the recommended solution (0-1)",
    )
    solution_source: Literal["llm", "heuristic"] = Field(
        default="llm",
        description="llm=structured output path; heuristic=offline/LLM-fallback builder",
    )
    risk_summary: str = Field(
        default="",
        description="Brief residual risks if the recommended solution is executed",
    )

    # D1 depth extensions (Category 1 + 5)
    assumptions: list[str] = Field(
        default_factory=list,
        description="Key assumptions made while forming the recommendation",
    )
    risks: list[RiskItem] = Field(
        default_factory=list,
        description="Structured residual risks with mitigation hints",
    )
    alternatives: str = Field(
        default="",
        description="Summary of other options considered and why the recommended one was chosen",
    )
    project_state_snapshot: str = Field(
        default="",
        description="Relevant snapshot of WBS / phase / known risks at analysis time (for explainability)",
    )

    # Explicit related knowledge field per strict prompt requirements
    related_knowledge: list[str] = Field(
        default_factory=list,
        description="Retrieved relevant historical case IDs or summaries from knowledge_base (e.g. 'kb-xxx: summary' or IDs)",
    )