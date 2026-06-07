"""Project Memory Manager — durable, outcome-aware, Grok-inspired memory for Forge.

M0 scope (persistence + memory pivot):
- Facade over existing knowledge_base + memory_graph.
- Ensures cross-run durability (graph carry + rebuild).
- Simple append for cases and execution outcomes (makes D3 execution feedback durable).
- Produces state patches consumable by LangGraph nodes / supervisor.
- Retrieval delegates to the proven search_similar_cases (enhanced in D work) for now.

Future (M1+): episodic store, incremental graph, vector hybrid, compaction, broader agent usage.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from forge.core.state import ProjectState
from forge.utils.knowledge import append_knowledge, append_knowledge_to_state

# M0: lazy imports to avoid package import cycles (core.memory.__init__ vs knowledge_memory).
# These are only needed inside methods.
def _get_km():
    from forge.utils import knowledge_memory as km
    return km

def _get_format_memory_context():
    return _get_km().format_memory_context

def _get_rebuild_memory_graph():
    return _get_km().rebuild_memory_graph

def _get_search_similar_cases():
    return _get_km().search_similar_cases


class ProjectMemory:
    """Lightweight manager for a project's long-term memory (per project_id).

    Holds references to the working kb/graph (usually coming from ProjectState).
    Provides high-level operations that multiple agents can call.

    This is the seed of the "独立 memory/ 包" called for in roadmaps.
    """

    def __init__(self, project_id: str, kb: list[dict[str, Any]] | None = None, graph: dict[str, Any] | None = None):
        self.project_id = project_id
        self.kb: list[dict[str, Any]] = list(kb or [])
        self.graph: dict[str, Any] = graph or {"nodes": [], "edges": []}

    @classmethod
    def from_state(cls, state: ProjectState | dict[str, Any]) -> "ProjectMemory":
        pid = state.get("project_id", "unknown") if isinstance(state, dict) else state.get("project_id", "unknown")
        kb = list(state.get("knowledge_base", []) if isinstance(state, dict) else state.get("knowledge_base", []))
        g = state.get("memory_graph") if isinstance(state, dict) else state.get("memory_graph")
        return cls(pid, kb=kb, graph=g)

    def to_state_patch(self) -> dict[str, Any]:
        """Return a minimal patch suitable for LangGraph state updates."""
        return {
            "knowledge_base": list(self.kb),
            "memory_graph": dict(self.graph),
        }

    # --- Writes (durable signals from the system) ---

    def append_case(
        self,
        *,
        summary: str,
        tags: list[str] | None = None,
        related_rules: list[str] | None = None,
        outcome: str | None = None,
        source: str = "memory_manager",
        detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append a distilled reusable case (semantic memory). Returns the created entry."""
        entry = append_knowledge(
            {"project_id": self.project_id, "knowledge_base": self.kb},  # minimal state-like for id gen
            agent=source,
            summary=summary,
            tags=tags,
            category="case",
            detail=detail,
        )
        entry["type"] = "case"
        entry["related_rules"] = related_rules or []
        entry["outcome"] = outcome
        self.kb.append(entry)
        self._refresh_graph()
        return entry

    def append_execution_outcome(
        self,
        *,
        task_id: str,
        status: str,
        summary: str,
        problem_type: str | None = None,
        related_solution_id: str | None = None,
    ) -> dict[str, Any]:
        """Write an execution result as durable memory (episodic → semantic bridge).

        This makes D3 "execution feedback closed loop" survive across saved runs/sessions.
        The entry is tagged so search_similar_cases and future retrieval can prefer or avoid patterns.
        """
        outcome = "success" if status in ("success", "completed", "ok") else (
            "failed" if status in ("failed", "error", "blocked") else "partial"
        )
        tags = ["execution", outcome]
        if problem_type:
            tags.append(problem_type)

        entry = append_knowledge(
            {"project_id": self.project_id, "knowledge_base": self.kb},
            agent="execution",
            summary=f"exec {task_id} [{status}]: {summary[:160]}",
            tags=tags,
            category="execution",
            detail={
                "task_id": task_id,
                "status": status,
                "related_solution_id": related_solution_id,
            },
        )
        entry["type"] = "execution_outcome"
        entry["outcome"] = outcome
        self.kb.append(entry)
        self._refresh_graph()
        return entry

    def _refresh_graph(self) -> None:
        """Rebuild the in-memory graph from current kb (M0: simple & correct; M1 can be incremental)."""
        self.graph = _get_rebuild_memory_graph()(self.kb)

    # --- Retrieval (for injection into agents) ---

    def search_similar_cases(
        self,
        *,
        problem_type: str,
        problem_text: str = "",
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        """Outcome- and rule-aware similar case retrieval (re-uses the strong D1-D3 implementation).

        Returns enriched entries with match_score / match_reason.
        """
        # We delegate to the existing function but feed it our durable kb/graph.
        # The function accepts dict-like state or ProjectState.
        fake_state: dict[str, Any] = {
            "project_id": self.project_id,
            "knowledge_base": self.kb,
            "memory_graph": self.graph,
        }
        return _get_search_similar_cases()(
            fake_state,
            problem_type=problem_type,
            problem_text=problem_text,
            limit=limit,
        )

    def format_context(self, entries: list[dict[str, Any]] | None = None) -> str:
        """Format for prompt injection (uses the D3-improved formatter with outcome/rules)."""
        if entries is None:
            # quick top-N recent positive if caller just wants "some memory"
            entries = [e for e in self.kb if e.get("outcome") in (None, "success", "compliant", "resolved", "partial")][-5:]
        return _get_format_memory_context()(entries)

    # --- Convenience ---

    def rebuild_graph(self) -> dict[str, Any]:
        self._refresh_graph()
        return self.graph

    def snapshot(self) -> dict[str, Any]:
        """Full snapshot for persistence or debugging."""
        return {
            "project_id": self.project_id,
            "knowledge_base": list(self.kb),
            "memory_graph": dict(self.graph),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


def get_memory(state: ProjectState | dict[str, Any]) -> ProjectMemory:
    """Convenience: get (or synthesize) a ProjectMemory from current working state."""
    return ProjectMemory.from_state(state)


def apply_memory_patch(state: ProjectState | dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Merge a memory patch (from manager.to_state_patch or extract_*) into a state update dict."""
    out: dict[str, Any] = {}
    if "knowledge_base" in patch:
        out["knowledge_base"] = list(patch["knowledge_base"])
    if "memory_graph" in patch:
        out["memory_graph"] = dict(patch["memory_graph"])
    return out