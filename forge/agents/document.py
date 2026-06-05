"""DocumentAgent — generate project documents aligned with standards."""

from __future__ import annotations

from typing import Any

from forge.agents.base import BaseAgent
from forge.core.state import ProjectState
from forge.prompts.document import DOCUMENT_SYSTEM
from forge.tools.document_generator import generate_document_outline
from forge.utils.llm import invoke_llm


class DocumentAgent(BaseAgent):
    """
    Phase 1 stub: produces structured document outlines.

    Phase 2 will generate full deliverables with template + Rule Pack alignment.
    """

    name = "document"

    def run(self, state: ProjectState) -> dict[str, Any]:
        messages = state.get("messages", [])
        request = ""
        if messages:
            request = getattr(messages[-1], "content", str(messages[-1]))

        outline = generate_document_outline(request, state)

        doc_ref = {
            "id": f"doc-{state['project_id']}-{len(state.get('documents', []))}",
            "title": outline.title,
            "doc_type": outline.doc_type,
            "path": None,
            "metadata": {"sections": outline.sections, "status": "outline"},
        }

        sections_text = "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(outline.sections))
        heuristic_body = (
            f"**Document**: {outline.title} ({outline.doc_type})\n\n**Outline**:\n{sections_text}"
        )
        llm_body = invoke_llm(
            DOCUMENT_SYSTEM,
            f"Request: {request}\n"
            f"Project phase: {state.get('current_phase')}\n"
            f"Proposed outline: {outline.sections}\n\n"
            "Expand the outline with section descriptions and compliance references.",
        )
        body = llm_body if llm_body else heuristic_body

        return {
            **self.reply(f"{DOCUMENT_SYSTEM}\n\n{body}"),
            "documents": state.get("documents", []) + [doc_ref],
            "pending_tasks": [
                t
                for t in state.get("pending_tasks", [])
                if not (t.get("assigned_to") == self.name and t.get("status") == "open")
            ],
        }


document_node = DocumentAgent()
