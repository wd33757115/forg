"""Forge Project Memory package (M0+).

Grok-inspired durable, structured, outcome-linked memory for project agents.
See docs/MEMORY_PERSISTENCE_DESIGN.md for architecture and roadmap.

M0 note: direct imports preferred to avoid cycles during early bootstrap:
  from forge.core.memory.graph import ...
  from forge.core.memory.manager import ProjectMemory, get_memory, apply_memory_patch
"""

# Only re-export the pure data model to keep import light.
# Manager has heavier (but lazy) dependencies.
from forge.core.memory.graph import MemoryGraph, MemoryNode, MemoryEdge

__all__ = [
    "MemoryGraph",
    "MemoryNode",
    "MemoryEdge",
    # Manager symbols are available via explicit submodule import.
]