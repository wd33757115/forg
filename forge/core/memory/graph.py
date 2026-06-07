"""Project Memory Graph — data model stub for v2.0."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class MemoryNode(BaseModel):
    """A node in the project memory graph."""

    id: str = Field(default_factory=lambda: f"mem-{uuid4().hex[:8]}")
    node_type: str  # case | rule | document | agent_output | task
    label: str
    properties: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MemoryEdge(BaseModel):
    """Directed edge between memory nodes."""

    id: str = Field(default_factory=lambda: f"edge-{uuid4().hex[:8]}")
    source_id: str
    target_id: str
    relation: str  # references | derived_from | supersedes | related_to
    weight: float = 1.0


class MemoryGraph(BaseModel):
    """In-memory graph snapshot attachable to ProjectState."""

    nodes: list[MemoryNode] = Field(default_factory=list)
    edges: list[MemoryEdge] = Field(default_factory=list)

    def add_node(self, node: MemoryNode) -> None:
        self.nodes.append(node)

    def add_edge(self, edge: MemoryEdge) -> None:
        self.edges.append(edge)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()

    @classmethod
    def from_knowledge_entries(cls, entries: list[dict[str, Any]]) -> "MemoryGraph":
        """Build a minimal graph from knowledge_base entries."""
        graph = cls()
        for entry in entries:
            nid = entry.get("id", f"kb-{len(graph.nodes)}")
            graph.add_node(
                MemoryNode(
                    id=nid,
                    node_type=entry.get("type", "case"),
                    label=(entry.get("content") or "")[:80],
                    properties={
                        "tags": entry.get("tags", []),
                        "source": entry.get("source"),
                        "outcome": entry.get("outcome"),
                    },
                )
            )
            for rule_id in entry.get("related_rules") or []:
                rule_nid = f"rule-{rule_id}"
                if not any(n.id == rule_nid for n in graph.nodes):
                    graph.add_node(
                        MemoryNode(id=rule_nid, node_type="rule", label=rule_id, properties={})
                    )
                graph.add_edge(
                    MemoryEdge(source_id=nid, target_id=rule_nid, relation="references")
                )
        return graph
