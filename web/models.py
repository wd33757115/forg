"""Pydantic request/response models for the Forge Web API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SolveRequest(BaseModel):
    """POST /solve request body."""

    question: str = Field(..., min_length=1, description="问题描述")
    project_id: str = Field(default="web-demo", description="项目 ID")
    protection_level: Literal["1", "2", "3", "4", "5"] = Field(
        default="3",
        description="等保保护级别",
    )
    scenario: Literal["security", "operations", "general", "auto"] = Field(
        default="auto",
        description="场景提示；auto 时根据问题关键词自动路由",
    )


class SolveResponse(BaseModel):
    """POST /solve response body."""

    success: bool
    run_id: str | None = None
    project_id: str | None = None
    question: str
    scenario: str = ""
    agents: list[str] = Field(default_factory=list)
    compliance_status: str | None = None
    risk_level: str | None = None
    compliance_retry_count: int = 0
    document_count: int = 0
    solution: dict[str, Any] | None = None
    compliance: dict[str, Any] | None = None
    security: dict[str, Any] | None = None
    operations: dict[str, Any] | None = None
    documents: list[dict[str, Any]] = Field(default_factory=list)
    pm_advice: dict[str, Any] | None = None
    workflow_plan: dict[str, Any] | None = None
    pipeline_trace: list[dict[str, Any]] = Field(default_factory=list)
    agent_errors: list[dict[str, Any]] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "forge"
