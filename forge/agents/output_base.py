"""Base class for all Forge agent structured outputs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class AgentOutputBase(BaseModel):
    """
    Common contract for agent Pydantic outputs.

    All specialist agents should return models inheriting this base so that
    serialization, persistence, and API responses stay consistent.
    """

    model_config = ConfigDict(extra="forbid")

    def to_state_dict(self) -> dict:
        """Dump to a JSON-serializable dict for ProjectState storage."""
        return self.model_dump()

    def to_display_json(self) -> str:
        """Pretty JSON for CLI / logs."""
        return self.model_dump_json(indent=2, ensure_ascii=False)
