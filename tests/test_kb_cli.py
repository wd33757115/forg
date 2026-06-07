"""Tests for kb CLI."""

from __future__ import annotations

from forge.cli.kb import kb_main
from forge.core.state import create_initial_state
from forge.utils.knowledge import append_knowledge, append_knowledge_to_state


def test_kb_search_by_tag(capsys):
    state = create_initial_state("kb-cli")
    entry = append_knowledge(state, agent="test", summary="等保案例", tags=["security"])
    state.update(append_knowledge_to_state(state, entry))

    from forge.utils.state_persistence import save_state

    path = save_state(state, ".forge_state/test_kb_cli.json")

    code = kb_main(["search", "--tag", "security", "--load-state", str(path)])
    assert code == 0
    out = capsys.readouterr().out
    assert "等保案例" in out or "security" in out
