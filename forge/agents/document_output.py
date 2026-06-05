"""Structured output models for DocumentAgent."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GeneratedDocument(BaseModel):
    """A single generated project document (Markdown / structured text)."""

    doc_id: str
    doc_type: str = Field(
        description="remediation_plan | technical_plan | dengbao_record | itil_incident | itil_problem | change_request"
    )
    title: str
    content: str = Field(description="Full document body in Markdown")
    format: str = "markdown"
    metadata: dict = Field(default_factory=dict)


class DocumentOutput(BaseModel):
    """Bundle of documents produced from solution + compliance context."""

    documents: list[GeneratedDocument] = Field(default_factory=list)
    summary: str = ""
    doc_types_generated: list[str] = Field(default_factory=list)

    def to_display_json(self) -> str:
        return self.model_dump_json(indent=2, ensure_ascii=False)
