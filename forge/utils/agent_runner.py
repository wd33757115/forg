"""Safe LangGraph node wrapper — pipeline tracing and error recovery."""

from __future__ import annotations

import traceback
from datetime import datetime, timezone
from typing import Any, Callable

from langchain_core.messages import AIMessage

from forge.core.state import ProjectState
from forge.utils.conversation import record_conversation
from forge.utils.logger import get_logger

# Agents whose failure should not abort the entire pipeline
OPTIONAL_AGENTS = frozenset({"security", "operations", "document", "pm_advisor"})


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_trace(state: ProjectState, entry: dict[str, Any]) -> list[dict[str, Any]]:
    trace = list(state.get("pipeline_trace", []))
    trace.append(entry)
    return trace


def wrap_agent_node(
    agent_fn: Callable[[ProjectState], dict[str, Any]],
    agent_name: str,
    *,
    optional: bool | None = None,
) -> Callable[[ProjectState], dict[str, Any]]:
    """
    Wrap an agent node with pipeline logging and graceful error handling.

    On failure:
    - Records error in ``agent_errors`` and ``pipeline_trace``
    - Optional agents: mark specialist complete and continue pipeline
    - Critical agents: record error but still return (downstream may degrade)
    """
    logger = get_logger("pipeline")
    is_optional = optional if optional is not None else agent_name in OPTIONAL_AGENTS

    def node(state: ProjectState) -> dict[str, Any]:
        run_id = state.get("run_id", "?")
        logger.info("[%s] ▶ agent=%s start", run_id, agent_name)

        start_entry = {
            "agent": agent_name,
            "status": "running",
            "timestamp": _utc_now(),
            "run_id": run_id,
        }

        try:
            updates = agent_fn(state)
            success_entry = {
                **start_entry,
                "status": "success",
                "finished_at": _utc_now(),
            }
            logger.info("[%s] ✓ agent=%s success", run_id, agent_name)

            merged: dict[str, Any] = dict(updates)
            merged["pipeline_trace"] = _append_trace(state, success_entry)
            return merged

        except Exception as exc:
            tb = traceback.format_exc()
            logger.error("[%s] ✗ agent=%s failed: %s", run_id, agent_name, exc)
            logger.debug(tb)

            error_record = {
                "agent": agent_name,
                "error": str(exc),
                "error_type": type(exc).__name__,
                "timestamp": _utc_now(),
                "traceback": tb[-2000:],
            }
            fail_entry = {
                **start_entry,
                "status": "failed",
                "error": str(exc),
                "finished_at": _utc_now(),
            }

            recovery: dict[str, Any] = {
                "agent_errors": list(state.get("agent_errors", [])) + [error_record],
                "pipeline_trace": _append_trace(state, fail_entry),
                "messages": [
                    AIMessage(
                        content=f"[{agent_name}] 执行失败（已记录，流程继续）: {exc}",
                        name=agent_name,
                    )
                ],
            }

            # Allow specialist chain to continue past failed optional agent
            if is_optional and agent_name in ("security", "operations"):
                done = list(state.get("specialists_completed", []))
                if agent_name not in done:
                    done.append(agent_name)
                recovery["specialists_completed"] = done

            recovery.update(
                record_conversation(
                    state,
                    agent=agent_name,
                    event="agent_error",
                    summary=f"{agent_name} 执行失败: {exc}",
                    detail=error_record,
                )
            )
            return recovery

    return node
