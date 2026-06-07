"""Pipeline trace helpers — input/output summaries per agent step."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from forge.core.state import ProjectState

_TRACE_TEXT_LIMIT = 220


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clip(text: str, limit: int = _TRACE_TEXT_LIMIT) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _last_user_message(state: ProjectState) -> str:
    for msg in reversed(state.get("messages") or []):
        content = getattr(msg, "content", msg)
        if content:
            return _clip(str(content), 160)
    return ""


def summarize_agent_input(state: ProjectState, agent_name: str) -> str:
    """Key input context visible to an agent before it runs."""
    if agent_name == "problem_solver":
        hint = state.get("problem_type_hint") or state.get("problem_type") or "auto"
        return f"问题: {_last_user_message(state)} | 类型提示={hint}"
    if agent_name == "compliance":
        sol = state.get("last_solution") or {}
        refs = len(sol.get("rule_pack_references") or [])
        return (
            f"方案={sol.get('recommended_solution_id', '—')} | "
            f"引用={refs} | mode={state.get('check_mode', 'advisory')} | "
            f"重试轮次={state.get('compliance_retry_count', 0)}"
        )
    if agent_name == "security":
        return f"问题类型={state.get('problem_type', '—')} | 方案已生成={bool(state.get('last_solution'))}"
    if agent_name == "operations":
        return f"问题类型={state.get('problem_type', '—')} | 运维上下文"
    if agent_name == "document":
        comp = state.get("last_compliance_result") or {}
        return (
            f"合规={comp.get('compliance_status', '—')} | "
            f"风险={comp.get('risk_level', '—')}"
        )
    if agent_name == "pm_advisor":
        docs = len(state.get("generated_documents") or [])
        return f"资料={docs} 份 | 合规={((state.get('last_compliance_result') or {}).get('compliance_status', '—'))}"
    if agent_name == "execution":
        return f"PM建议={'有' if state.get('last_pm_advice') else '无'} | 合规缺口={len((state.get('last_compliance_result') or {}).get('missing_items') or [])}"
    if agent_name == "approval_gate":
        return f"置信度={state.get('confidence_score', '—')} | 建议={state.get('confidence_recommendation', '—')}"
    return _last_user_message(state) or f"project={state.get('project_id', '?')}"


def summarize_agent_output(
    state: ProjectState,
    agent_name: str,
    updates: dict[str, Any],
) -> str:
    """Short summary of what the agent produced."""
    merged = {**state, **updates}
    if agent_name == "problem_solver":
        sol = merged.get("last_solution") or {}
        return _clip(
            f"{sol.get('recommended_solution_id', '—')} | "
            f"type={sol.get('problem_type', '—')} | "
            f"refs={len(sol.get('rule_pack_references') or [])} | "
            f"{(sol.get('problem_analysis') or '')[:80]}"
        )
    if agent_name == "compliance":
        comp = merged.get("last_compliance_result") or {}
        missing = len(comp.get("missing_items") or [])
        return (
            f"status={comp.get('compliance_status', comp.get('overall_status', '—'))} | "
            f"risk={comp.get('risk_level', '—')} | gaps={missing}"
        )
    if agent_name == "security":
        sec = merged.get("last_security_result") or {}
        return _clip(sec.get("diagnosis") or sec.get("summary") or "—")
    if agent_name == "operations":
        ops = merged.get("last_operations_result") or {}
        return _clip(ops.get("situation_summary") or "—")
    if agent_name == "document":
        docs = merged.get("generated_documents") or []
        if not docs:
            return "未生成资料"
        types = ", ".join(d.get("doc_type", "?") for d in docs[:4])
        return f"{len(docs)} 份 ({types})"
    if agent_name == "pm_advisor":
        pm = merged.get("last_pm_advice") or {}
        actions = len(pm.get("action_items") or [])
        return _clip(f"{pm.get('summary', '')[:100]} | 行动项={actions}")
    if agent_name == "execution":
        tasks = merged.get("execution_tasks") or []
        return f"任务={len(tasks)} | 置信度={merged.get('confidence_score', '—')}"
    if agent_name == "approval_gate":
        return f"审批={merged.get('approval_status', '—')} | pending={len(merged.get('pending_approvals') or [])}"
    return "完成"


def append_pipeline_trace(state: ProjectState, entry: dict[str, Any]) -> list[dict[str, Any]]:
    trace = list(state.get("pipeline_trace", []))
    trace.append(entry)
    return trace


def build_supervisor_trace_entry(
    state: ProjectState,
    *,
    event: str,
    detail: str,
    next_agent: str | None = None,
    input_summary: str = "",
    output_summary: str = "",
) -> dict[str, Any]:
    return {
        "agent": "supervisor",
        "node": event,
        "status": "success",
        "timestamp": _utc_now(),
        "run_id": state.get("run_id", "?"),
        "check_mode": state.get("check_mode"),
        "retry_generation": int(state.get("compliance_retry_count") or 0),
        "detail": detail,
        "next_agent": next_agent,
        "input_summary": input_summary or summarize_agent_input(state, "supervisor"),
        "output_summary": output_summary or (f"→ {next_agent}" if next_agent else detail),
    }
