"""Safe LangGraph node wrapper — pipeline tracing and error recovery."""

from __future__ import annotations

import time
import traceback
from datetime import datetime, timezone
from typing import Any, Callable

from langchain_core.messages import AIMessage

from forge.core.state import ProjectState
from forge.utils.conversation import record_conversation
from forge.utils.logger import get_logger
from forge.utils.trace import (
    append_pipeline_trace,
    summarize_agent_input,
    summarize_agent_output,
)

# Agents whose failure should not abort the entire pipeline
OPTIONAL_AGENTS = frozenset({"security", "operations", "document", "pm_advisor"})

# Degraded empty payloads so downstream nodes can continue
_DEGRADED_PAYLOADS: dict[str, dict[str, Any]] = {
    "security": {"last_security_result": None, "degraded_agents": ["security"]},
    "operations": {"last_operations_result": None, "degraded_agents": ["operations"]},
    "document": {"generated_documents": [], "degraded_agents": ["document"]},
    "pm_advisor": {"last_pm_advice": None, "degraded_agents": ["pm_advisor"]},
    "problem_solver": {"last_solution": None, "degraded_agents": ["problem_solver"]},
    "compliance": {
        "last_compliance_result": {
            "compliance_status": "partial",
            "overall_status": "gaps_found",
            "risk_level": "medium",
            "missing_items": ["合规检查未完成（Agent 异常降级）"],
            "recommendations": ["人工复核合规结果后重新运行 ComplianceAgent"],
        },
        "degraded_agents": ["compliance"],
    },
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
        t0 = time.perf_counter()
        check_mode = state.get("check_mode")
        retry_generation = int(state.get("compliance_retry_count") or 0)

        input_summary = summarize_agent_input(state, agent_name)
        start_entry = {
            "agent": agent_name,
            "status": "running",
            "timestamp": _utc_now(),
            "run_id": run_id,
            "check_mode": check_mode,
            "retry_generation": retry_generation,
            "input_summary": input_summary,
        }

        try:
            updates = agent_fn(state)
            duration_ms = round((time.perf_counter() - t0) * 1000, 1)
            output_summary = summarize_agent_output(state, agent_name, updates)
            success_entry = {
                **start_entry,
                "status": "success",
                "finished_at": _utc_now(),
                "duration_ms": duration_ms,
                "output_summary": output_summary,
                "detail": output_summary,
            }
            logger.info("[%s] ✓ agent=%s success | %s", run_id, agent_name, output_summary)

            merged: dict[str, Any] = dict(updates)
            merged["pipeline_trace"] = append_pipeline_trace(state, success_entry)
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
            duration_ms = round((time.perf_counter() - t0) * 1000, 1)
            fail_entry = {
                **start_entry,
                "status": "failed",
                "error": str(exc),
                "finished_at": _utc_now(),
                "duration_ms": duration_ms,
                "output_summary": f"失败: {exc}",
                "detail": str(exc),
            }

            recovery: dict[str, Any] = {
                "agent_errors": list(state.get("agent_errors", [])) + [error_record],
                "pipeline_trace": append_pipeline_trace(state, fail_entry),
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

            degraded = _DEGRADED_PAYLOADS.get(agent_name, {})
            if degraded:
                existing_degraded = list(state.get("degraded_agents", []))
                for tag in degraded.get("degraded_agents", []):
                    if tag not in existing_degraded:
                        existing_degraded.append(tag)
                recovery["degraded_agents"] = existing_degraded
                for key, value in degraded.items():
                    if key != "degraded_agents":
                        recovery[key] = value

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
