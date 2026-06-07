"""Execution layer data models (v1.1)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

ExecutionTaskStatus = Literal["draft", "pending_approval", "ready", "blocked", "executed", "failed"]
ExecutionTaskType = Literal["remediation", "project_action", "implementation_wbs", "change_request"]


class ExecutionTask(BaseModel):
    """A unit of work generated from compliance / PM artifacts."""

    id: str
    task_type: ExecutionTaskType
    title: str
    description: str = ""
    status: ExecutionTaskStatus = "draft"
    priority: str = "P2"
    source: str = "compliance"
    related_rules: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_state_dict(self) -> dict[str, Any]:
        return self.model_dump()


class ExecutionResult(BaseModel):
    """Outcome of a simulated execution (no external system integration)."""

    task_id: str
    status: Literal["success", "failed", "skipped"] = "success"
    summary: str = ""
    executed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_state_dict(self) -> dict[str, Any]:
        return self.model_dump()
