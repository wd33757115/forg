"""Structured output models for SecurityAgent (等保2.0 focus)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SecurityControlAdvice(BaseModel):
    """Configuration advice for a security control domain."""

    control_id: str
    domain: str = Field(description="firewall | audit | access_control | boundary | host | other")
    title: str
    recommendation: str
    priority: str = Field(description="high | medium | low")


class SecurityRiskItem(BaseModel):
    """A identified security risk."""

    title: str
    severity: str = Field(description="low | medium | high | critical")
    description: str = ""
    remediation: str = ""


class SecurityOutput(BaseModel):
    """
    Structured 等保2.0 security advisory report.

    Covers diagnosis, configuration advice, risk assessment, and assessment materials.
    """

    diagnosis: str = Field(description="等保问题诊断结论")
    protection_level: str = Field(default="3", description="Applicable 等保 protection level 1-5")
    risk_assessment: str = Field(description="Overall security risk narrative")
    risk_level: str = Field(description="low | medium | high | critical")
    security_risks: list[SecurityRiskItem] = Field(default_factory=list)
    remediation_items: list[str] = Field(default_factory=list)
    configuration_advice: list[SecurityControlAdvice] = Field(default_factory=list)
    assessment_materials: list[str] = Field(
        default_factory=list,
        description="Suggested evidence/documents for 等保测评",
    )
    dengbao_rule_references: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)

    def to_display_json(self) -> str:
        return self.model_dump_json(indent=2, ensure_ascii=False)
