"""ComplianceAgent — multi-standard compliance checks (等保2.0 + ITIL/ISO20000)."""

from __future__ import annotations

from typing import Any

from forge.agents.base import BaseAgent
from forge.core.rule_pack import get_rule_pack
from forge.core.state import ProjectState
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

        record = {
            "id": f"cmp-{state['project_id']}-{len(state.get('compliance_history', []))}",
            "standard": ",".join(modules),
            "rule_id": "batch_scan",
            "status": scan.overall_status,
            "findings": scan.findings,
            "checked_at": scan.checked_at,
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
            "pending_tasks": [
                t
                for t in state.get("pending_tasks", [])
                if not (t.get("assigned_to") == self.name and t.get("status") == "open")
            ],
        }


compliance_node = ComplianceAgent()
