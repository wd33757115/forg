"""Approval flow data models (v1.1)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

ApprovalStatus = Literal["pending", "approved", "rejected", "auto_approved", "blocked"]


class ApprovalRequest(BaseModel):
    """Human or auto approval gate for execution tasks."""

    id: str
    status: ApprovalStatus = "pending"
    recommendation: str = "needs_review"
    confidence_score: float = 0.0
    risk_level: str | None = None
    reason: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: str | None = None
    resolved_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_state_dict(self) -> dict[str, Any]:
        return self.model_dump()
