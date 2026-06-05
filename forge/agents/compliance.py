"""ComplianceAgent — multi-standard compliance checks (等保2.0 + ITIL/ISO20000)."""

from __future__ import annotations

from typing import Any

from forge.agents.base import BaseAgent
from forge.core.rule_pack_loader import get_rule_pack
from forge.core.state import ComplianceResult, ProjectState
from forge.prompts.compliance import COMPLIANCE_SYSTEM
from forge.tools.compliance_checker import run_compliance_scan
from forge.utils.llm import invoke_llm


class ComplianceAgent(BaseAgent):
    """
    Phase 1 stub: scans enabled Rule Packs against project artifacts.

    Phase 2 will add evidence mapping, gap reports, and remediation plans.
    """

    name = "compliance"

    def run(self, state: ProjectState) -> dict[str, Any]:
        modules = tuple(state.get("enabled_modules", []))
        packs = get_rule_pack(modules)
        scan = run_compliance_scan(state, packs)

        pack_meta = state.get("rule_pack") or {}
        result = ComplianceResult(
            id=f"cmp-{state['project_id']}-{len(state.get('compliance_results', []))}",
            pack_id=pack_meta.get("pack_id", "unknown"),
            modules=list(modules),
            status=scan.overall_status,
            findings=scan.findings,
            checked_at=scan.checked_at,
        )
        record = {
            "id": result.id,
            "standard": ",".join(modules),
            "rule_id": "batch_scan",
            "status": result.status,
            "findings": result.findings,
            "checked_at": result.checked_at,
        }

        findings_text = "\n".join(f"- {f}" for f in scan.findings) if scan.findings else "- None"
        heuristic_body = (
            f"**Scan status**: {scan.overall_status}\n\n"
            f"**Findings** ({len(scan.findings)}):\n{findings_text}"
        )
        llm_body = invoke_llm(
            COMPLIANCE_SYSTEM,
            f"Project phase: {state.get('current_phase')}\n"
            f"Enabled modules: {state.get('enabled_modules')}\n"
            f"Compliance scan results:\n{heuristic_body}\n\n"
            "Provide a concise remediation plan citing relevant standards.",
        )
        body = llm_body if llm_body else heuristic_body

        return {
            **self.reply(f"{COMPLIANCE_SYSTEM}\n\n{body}"),
            "compliance_history": state.get("compliance_history", []) + [record],
            "compliance_results": state.get("compliance_results", [])
            + [result.model_dump()],
            "pending_tasks": [
                t
                for t in state.get("pending_tasks", [])
                if not (t.get("assigned_to") == self.name and t.get("status") == "open")
            ],
        }


compliance_node = ComplianceAgent()
