"""ProblemSolverAgent — diagnose issues and propose remediation paths."""

from __future__ import annotations

from typing import Any

from forge.agents.base import BaseAgent
from forge.core.rule_pack_loader import get_rule_pack
from forge.core.state import ProjectState
from forge.prompts.problem_solver import PROBLEM_SOLVER_SYSTEM
from forge.tools.diagnostics import analyze_symptoms
from forge.utils.llm import invoke_llm


class ProblemSolverAgent(BaseAgent):
    """
    Phase 1 stub: rule-based diagnosis scaffold.

    Phase 2 will wire LLM + tools for root-cause analysis and WBS impact mapping.
    """

    name = "problem_solver"

    def run(self, state: ProjectState) -> dict[str, Any]:
        messages = state.get("messages", [])
        last_content = ""
        if messages:
            last_content = getattr(messages[-1], "content", str(messages[-1]))

        packs = get_rule_pack(tuple(state.get("enabled_modules", [])))
        diagnosis = analyze_symptoms(last_content, packs)

        knowledge_entry = {
            "id": f"kb-{state['project_id']}-ps-{len(state.get('knowledge_base', []))}",
            "category": "problem_pattern",
            "content": diagnosis.summary,
            "source": self.name,
            "tags": diagnosis.tags,
        }

        actions_text = "\n".join(f"- {a}" for a in diagnosis.actions)
        heuristic_body = f"**Diagnosis**: {diagnosis.summary}\n\n**Recommended actions**:\n{actions_text}"
        llm_body = invoke_llm(
            PROBLEM_SOLVER_SYSTEM,
            f"User report: {last_content}\n\n"
            f"Preliminary diagnosis: {diagnosis.summary}\n"
            f"Suggested actions: {diagnosis.actions}\n\n"
            "Expand into root-cause analysis with options A/B/C.",
        )
        body = llm_body if llm_body else heuristic_body

        return {
            **self.reply(f"{PROBLEM_SOLVER_SYSTEM}\n\n{body}"),
            "knowledge_base": state.get("knowledge_base", []) + [knowledge_entry],
            "pending_tasks": [
                t
                for t in state.get("pending_tasks", [])
                if not (t.get("assigned_to") == self.name and t.get("status") == "open")
            ],
        }


problem_solver_node = ProblemSolverAgent()
