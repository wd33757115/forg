"""DocumentAgent — generate project documents from solution + compliance."""

from __future__ import annotations

from typing import Any

from forge.core.base_agent import BaseAgent
from forge.agents.document_output import DocumentOutput
from forge.core.state import ProjectState
from forge.prompts.document_prompt import DOCUMENT_SYSTEM
from forge.utils.conversation import record_conversation
from forge.utils.llm import invoke_llm
from forge.utils.logger import get_logger

logger = get_logger("document")


class DocumentAgent(BaseAgent):
    """
    Generate structured project documents based on ProblemSolver solution
    and ComplianceAgent results.

    Produces Markdown documents (upgradeable to python-docx templates later):
    - 整改方案 / 技术方案
    - 等保整改记录
    - ITIL 事件/问题记录
    - 变更申请记录
    """

    name = "document"

    def generate(
        self,
        state: ProjectState,
        *,
        solution: dict[str, Any] | None = None,
        compliance: dict[str, Any] | None = None,
    ) -> DocumentOutput:
        """Core generation via ToolRegistry ``generate_project_documents`` tool."""
        solution = solution or state.get("last_solution") or {}
        compliance = compliance or state.get("last_compliance_result") or {}

        tools = {t.name: t for t in self.get_tools(state)}
        gen_tool = tools.get("generate_project_documents")
        if gen_tool is None:
            raise RuntimeError("DocumentAgent: generate_project_documents not registered in ToolRegistry")

        bundle = DocumentOutput.model_validate_json(gen_tool.invoke({}))

        # Optional LLM enrichment of summary
        llm_summary = invoke_llm(
            DOCUMENT_SYSTEM,
            f"方案: {solution.get('problem_analysis', '')[:500]}\n"
            f"合规: {compliance.get('compliance_status', '')} — "
            f"{len(compliance.get('missing_items', []))} 项缺口\n"
            "用一句话总结已生成资料包的价值。",
        )
        if llm_summary:
            bundle.summary = llm_summary

        return bundle

    def _format_response(self, output: DocumentOutput) -> str:
        lines = [
            "## 资料生成完成",
            output.summary,
            "",
            f"共 **{len(output.documents)}** 份文档：",
        ]
        for doc in output.documents:
            lines.append(f"- [{doc.doc_type}] **{doc.title}** (`{doc.doc_id}`)")
            preview = doc.content[:200].replace("\n", " ")
            lines.append(f"  > {preview}…")
        return "\n".join(lines)

    def run(self, state: ProjectState) -> dict[str, Any]:
        """LangGraph node entrypoint."""
        output = self.generate(state)

        generated_records = [
            {
                "doc_id": doc.doc_id,
                "doc_type": doc.doc_type,
                "title": doc.title,
                "format": doc.format,
                "content": doc.content,
                "metadata": doc.metadata,
            }
            for doc in output.documents
        ]

        # Legacy documents list (title refs for compliance checks)
        doc_refs = [
            {
                "id": doc.doc_id,
                "title": doc.title,
                "doc_type": doc.doc_type,
                "path": None,
                "metadata": {"format": doc.format, "status": "generated"},
            }
            for doc in output.documents
        ]

        logger.info("Generated %d documents: %s", len(output.documents), output.doc_types_generated)

        agent_updates: dict[str, Any] = {
            **self.reply(self._format_response(output)),
            "generated_documents": state.get("generated_documents", []) + generated_records,
            "documents": state.get("documents", []) + doc_refs,
            "pending_tasks": [
                t
                for t in state.get("pending_tasks", [])
                if not (t.get("assigned_to") == self.name and t.get("status") == "open")
            ],
        }
        agent_updates.update(
            record_conversation(
                state,
                agent=self.name,
                event="documents_generated",
                summary=output.summary,
                detail={"doc_types": output.doc_types_generated, "count": len(output.documents)},
            )
        )
        return agent_updates


document_node = DocumentAgent()
