"""ProjectState — the shared memory layer for all Forge agents."""

from __future__ import annotations

from typing import Annotated, Any

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from forge.core.rule_pack import Rule, RuleModule, RulePack

# Re-export Rule Pack models for consumers that import from state
__all__ = [
    "ComplianceRecord",
    "ComplianceResult",
    "DocumentRef",
    "KnowledgeEntry",
    "PendingTask",
    "ProjectState",
    "Rule",
    "RuleModule",
    "RulePack",
    "RulePackState",
    "WBSItem",
    "WORKFLOW_PROBLEM_COMPLIANCE_LOOP",
    "create_initial_state",
]

# Closed-loop workflow identifier: ProblemSolver → Compliance → (retry) → finalize
WORKFLOW_PROBLEM_COMPLIANCE_LOOP = "problem_compliance_loop"


class WBSItem(BaseModel):
    """Work Breakdown Structure node."""

    id: str
    name: str
    status: str = "pending"
    owner: str | None = None
    progress: float = 0.0
    children: list[str] = Field(default_factory=list)


class DocumentRef(BaseModel):
    """Reference to a project document or artifact."""

    id: str
    title: str
    doc_type: str
    path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComplianceRecord(BaseModel):
    """A compliance check or audit event (legacy field: compliance_history)."""

    id: str
    standard: str
    rule_id: str
    status: str
    findings: list[str] = Field(default_factory=list)
    checked_at: str | None = None


class ComplianceResult(BaseModel):
    """Structured compliance scan result stored in ProjectState.compliance_results."""

    id: str
    pack_id: str
    modules: list[str] = Field(default_factory=list)
    status: str
    findings: list[str] = Field(default_factory=list)
    checked_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RulePackState(BaseModel):
    """Snapshot of the active Rule Pack attached to a project session."""

    pack_id: str
    name: str
    version: str
    enabled_modules: list[str] = Field(default_factory=list)


class KnowledgeEntry(BaseModel):
    """Structured knowledge stored in the project brain."""

    id: str
    category: str
    content: str
    source: str | None = None
    tags: list[str] = Field(default_factory=list)


class PendingTask(BaseModel):
    """Work item awaiting agent or human action."""

    id: str
    title: str
    assigned_to: str
    priority: str = "medium"
    status: str = "open"
    context: dict[str, Any] = Field(default_factory=dict)


class ProjectState(TypedDict):
    """
    Shared state passed through the LangGraph workflow.

    All agents read from and write to this structure. Messages use LangGraph's
    add_messages reducer so conversation history accumulates correctly.
    """

    project_id: str
    current_phase: str
    enabled_modules: list[str]
    wbs: dict[str, Any]
    documents: list[dict[str, Any]]
    compliance_history: list[dict[str, Any]]
    compliance_results: list[dict[str, Any]]
    knowledge_base: list[dict[str, Any]]
    messages: Annotated[list, add_messages]
    pending_tasks: list[dict[str, Any]]
    rule_pack: dict[str, Any] | None
    # Closed-loop control (ProblemSolver ↔ Compliance ↔ Document)
    compliance_retry_count: int
    last_solution: dict[str, Any] | None
    last_compliance_result: dict[str, Any] | None
    generated_documents: list[dict[str, Any]]
    last_pm_advice: dict[str, Any] | None
    final_output: dict[str, Any] | None
    conversation_history: list[dict[str, Any]]
    active_workflow: str | None
    workflow_step: str | None
    # Supervisor routing hint — set by supervisor, consumed by conditional edges
    next_agent: str | None


def create_initial_state(
    project_id: str,
    *,
    current_phase: str = "initiation",
    enabled_modules: list[str] | None = None,
    rule_pack: dict[str, Any] | None = None,
) -> ProjectState:
    """Create a fresh ProjectState for a new project session."""
    return ProjectState(
        project_id=project_id,
        current_phase=current_phase,
        enabled_modules=enabled_modules or ["base_si", "dengbao_2.0", "itil_iso20000"],
        wbs={},
        documents=[],
        compliance_history=[],
        compliance_results=[],
        knowledge_base=[],
        messages=[],
        pending_tasks=[],
        rule_pack=rule_pack,
        compliance_retry_count=0,
        last_solution=None,
        last_compliance_result=None,
        generated_documents=[],
        last_pm_advice=None,
        final_output=None,
        conversation_history=[],
        active_workflow=None,
        workflow_step=None,
        next_agent=None,
    )
