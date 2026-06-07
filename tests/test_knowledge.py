"""Tests for knowledge_base helpers."""

from __future__ import annotations

from forge.core.state import create_initial_state
from forge.utils.knowledge import (
    append_knowledge,
    append_knowledge_to_state,
    format_knowledge_context,
    search_knowledge,
)


def test_append_and_search_by_tag():
    state = create_initial_state("kb-test")
    entry = append_knowledge(
        state,
        agent="problem_solver",
        summary="等保401故障已修复",
        tags=["security", "resolved"],
        category="case",
    )
    state["knowledge_base"] = [entry]
    found = search_knowledge(state, tags=["security"])
    assert len(found) == 1
    assert found[0]["content"].startswith("等保")


def test_search_by_agent():
    state = create_initial_state("kb-agent")
    state["knowledge_base"] = [
        append_knowledge(state, agent="compliance", summary="a", tags=["x"]),
        append_knowledge(state, agent="problem_solver", summary="b", tags=["x"]),
    ]
    found = search_knowledge(state, agent="compliance")
    assert len(found) == 1
    assert found[0]["source"] == "compliance"


def test_format_knowledge_context_empty():
    assert "无相关" in format_knowledge_context([])


def test_append_knowledge_to_state():
    state = create_initial_state("kb-append")
    entry = append_knowledge(state, agent="test", summary="案例", tags=["security"])
    update = append_knowledge_to_state(state, entry)
    assert len(update["knowledge_base"]) == 1
    assert update["knowledge_base"][0]["content"] == "案例"


def test_append_knowledge_with_item_dict():
    state = create_initial_state("kb-item")
    custom = {"id": "kb-custom-1", "content": "raw", "source": "import", "tags": []}
    entry = append_knowledge(state, agent="x", summary="", item=custom)
    assert entry["id"] == "kb-custom-1"


def test_search_knowledge_keywords_and_match_all_tags():
    state = create_initial_state("kb-kw")
    state["knowledge_base"] = [
        {
            "id": "1",
            "content": "等保三级登录故障案例",
            "tags": ["security", "auth"],
            "source": "a",
        },
        {
            "id": "2",
            "content": "ITIL 事件管理",
            "tags": ["itil", "auth"],
            "source": "b",
        },
    ]
    hits = search_knowledge(state, tags=["security", "auth"], match_all_tags=True)
    assert len(hits) == 1
    assert hits[0]["id"] == "1"
    kw_hits = search_knowledge(state, keywords=["登录", "等保"])
    assert kw_hits[0]["id"] == "1"


def test_record_handoff_in_conversation():
    from forge.utils.agent_context import build_handoff
    from forge.utils.conversation import record_handoff

    state = create_initial_state("handoff-test")
    state.update(
        build_handoff(
            state,
            from_agent="problem_solver",
            to_agent="compliance",
            payload={"rule_pack_references": [], "problem_type": "security"},
        )
    )
    handoffs = [h for h in state["conversation_history"] if h.get("event") == "handoff"]
    assert len(handoffs) == 1
    assert handoffs[0]["detail"]["to_agent"] == "compliance"

    # direct API
    state2 = create_initial_state("handoff-2")
    state2.update(record_handoff(state2, from_agent="a", to_agent="b", payload_keys=["k"]))
    assert state2["conversation_history"][0]["event"] == "handoff"
