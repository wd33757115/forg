"""Plain-text result printing for Forge CLI."""

from __future__ import annotations

from forge.cli.ansi import bold, cyan, dim, green, red, section, wrap_text, yellow
from forge.utils.llm import resolve_llm_config

AGENT_DISPLAY = {
    "ProblemSolver": ("问题分析", "last_solution", "problem_analysis"),
    "Security": ("等保安全", "last_security_result", "diagnosis"),
    "Operations": ("ITIL运维", "last_operations_result", "situation_summary"),
    "Compliance": ("合规检查", "last_compliance_result", "compliance_status"),
    "Document": ("资料生成", "generated_documents", None),
    "PMAdvisor": ("PM总结", "last_pm_advice", "summary"),
}


def _priority_color(priority: str) -> str:
    p = priority.upper()
    if p == "P0":
        return red(priority)
    if p == "P1":
        return yellow(priority)
    return dim(priority)


def _get_recommended_solution(solution: dict) -> dict:
    rec_id = solution.get("recommended_solution_id", "")
    for sol in solution.get("solutions", []):
        if sol.get("id") == rec_id:
            return sol
    solutions = solution.get("solutions", [])
    return solutions[0] if solutions else {}


def print_pipeline_summary(result: dict) -> None:
    plan = result.get("workflow_plan") or result.get("final_output", {}).get("workflow_plan") or {}
    trace = result.get("pipeline_trace") or result.get("final_output", {}).get("pipeline_trace") or []

    if not plan and not trace:
        return

    section("执行流水线 (Pipeline)")
    if plan.get("stages"):
        print(dim(f"  计划: {' → '.join(plan['stages'])}"))
        print(dim(f"  场景: {plan.get('scenario', 'N/A')} | 工作流: {plan.get('workflow', 'N/A')}"))
    if trace:
        print(dim("\n  实际执行:"))
        for entry in trace:
            status = entry.get("status", "?")
            agent = entry.get("agent", "?")
            icon = green("✓") if status == "success" else (red("✗") if status == "failed" else "…")
            err = f" — {entry.get('error', '')}" if status == "failed" else ""
            print(f"    {icon} {agent:<18} {status}{err}")


def print_agent_errors(result: dict) -> None:
    errors = result.get("agent_errors") or result.get("final_output", {}).get("agent_errors") or []
    degraded = result.get("degraded_agents") or []
    if not errors and not degraded:
        return
    section("执行异常与降级 (Errors & Degradation)")
    for err in errors:
        etype = err.get("error_type", "")
        suffix = f" [{etype}]" if etype else ""
        print(red(f"  ✗ {err.get('agent', '?')}: {err.get('error', '')}{suffix}"))
    if degraded:
        print(yellow(f"  ⚠ 已降级跳过的 Agent: {', '.join(degraded)}"))


def print_agent_contributions(result: dict) -> None:
    trace = result.get("pipeline_trace") or []
    if not trace:
        return

    section("Agent 贡献摘要")
    status_map = {e.get("agent"): e.get("status") for e in trace}

    for agent_name, (label, state_key, preview_field) in AGENT_DISPLAY.items():
        trace_key = agent_name.lower() if agent_name != "ProblemSolver" else "problem_solver"
        if agent_name == "PMAdvisor":
            trace_key = "pm_advisor"
        status = status_map.get(trace_key, "—")
        if status == "success":
            icon = green("✓")
        elif status == "failed":
            icon = red("✗")
        elif status == "running":
            icon = yellow("…")
        else:
            icon = dim("○")

        payload = result.get(state_key)
        if state_key == "generated_documents":
            preview = f"{len(payload or [])} 份资料" if payload else "未生成"
        elif payload and preview_field:
            val = payload.get(preview_field, "") if isinstance(payload, dict) else str(payload)
            preview = (str(val)[:72] + "…") if len(str(val)) > 72 else str(val)
        elif payload:
            preview = "已产出"
        else:
            preview = dim("无输出")

        print(f"  {icon} {bold(agent_name):<16} {dim(label):<10} {preview}")


def print_security_result(result: dict) -> None:
    final = result.get("final_output") or {}
    sec = final.get("security") or result.get("last_security_result") or {}
    if not sec:
        return

    section("等保安全分析 (SecurityAgent)")
    print(wrap_text(sec.get("diagnosis", "")))
    print(
        dim(
            f"\n  保护级别: {sec.get('protection_level', 'N/A')}  |  "
            f"风险: {sec.get('risk_level', 'N/A')}"
        )
    )
    for r in sec.get("security_risks", [])[:6]:
        print(f"    • {r.get('title', '')} [{r.get('severity', '')}]")
    for c in sec.get("configuration_advice", [])[:5]:
        print(f"    → [{c.get('domain')}] {c.get('title')}")


def print_operations_result(result: dict) -> None:
    final = result.get("final_output") or {}
    ops = final.get("operations") or result.get("last_operations_result") or {}
    if not ops:
        return

    section("ITIL 运维分析 (OperationsAgent)")
    print(wrap_text(ops.get("situation_summary", "")))
    print(dim(f"\n  实践域: {ops.get('practice_area', 'N/A')}"))
    ig = ops.get("incident_guidance")
    if ig:
        print(dim(f"  事件优先级: {ig.get('priority', 'N/A')} | 影响: {ig.get('impact', '')}"))
        for step in ig.get("response_steps", [])[:5]:
            print(f"    → {step}")


def print_pm_advisor(result: dict) -> None:
    final = result.get("final_output") or {}
    pm = final.get("pm_advice") or result.get("last_pm_advice") or {}
    if not pm:
        section("项目经理视角总结 (PMAdvisor)")
        print(yellow("  （未生成 PM 顾问报告）"))
        return

    section("项目经理视角总结 (PMAdvisor)")
    print(bold("\n  执行摘要"))
    print(wrap_text(pm.get("summary", ""), indent=4))
    for a in pm.get("action_items", [])[:8]:
        pri = _priority_color(a.get("priority", "P2"))
        print(f"    [{pri}] {a.get('title', '')} — {a.get('owner', '待定')}")


def _agents_contributed(result: dict) -> list[str]:
    agents: list[str] = []
    if result.get("last_solution"):
        agents.append("ProblemSolver")
    if result.get("last_security_result"):
        agents.append("Security")
    if result.get("last_operations_result"):
        agents.append("Operations")
    if result.get("last_compliance_result"):
        agents.append("Compliance")
    if result.get("generated_documents"):
        agents.append("Document")
    if result.get("last_pm_advice"):
        agents.append("PMAdvisor")
    return agents


def print_result(result: dict, *, question: str = "") -> None:
    """Pretty-print the full Forge execution result."""
    final = result.get("final_output") or {}
    solution = final.get("solution") or result.get("last_solution") or {}
    compliance = final.get("compliance") or result.get("last_compliance_result") or {}
    docs = final.get("generated_documents") or result.get("generated_documents", [])
    retries = result.get("compliance_retry_count", 0)
    history = result.get("conversation_history", [])
    run_id = result.get("run_id") or final.get("run_id", "")

    if question:
        section("用户问题")
        print(wrap_text(question))
    if run_id:
        print(dim(f"  运行 ID: {run_id}"))

    print_pipeline_summary(result)

    section("问题分析 (ProblemSolver)")
    if solution:
        ptype = solution.get("problem_type", result.get("problem_type", ""))
        if ptype:
            print(dim(f"  问题类型: {ptype}"))
        print(wrap_text(solution.get("problem_analysis", "无分析结果")))
        for c in solution.get("root_causes", []):
            print(f"    • {c}")
        refs = solution.get("rule_pack_references") or []
        if refs:
            print(dim("\n  Rule Pack 引用:"))
            for r in refs[:5]:
                print(f"    • [{r.get('rule_id')}] {r.get('title')}")
    else:
        print(yellow("  （无方案输出）"))

    section("推荐方案")
    if solution:
        rec = _get_recommended_solution(solution)
        print(f"  {green('★')} 方案 ID: {bold(solution.get('recommended_solution_id', 'N/A'))}")
        print(f"  标题: {bold(rec.get('title', 'N/A'))}")
        print(wrap_text(rec.get("description", "")))
    else:
        print(yellow("  （无推荐方案）"))

    print_security_result(result)
    print_operations_result(result)

    section("合规检查结果 (Compliance)")
    comp_status = compliance.get("compliance_status", compliance.get("overall_status", "unknown"))
    risk = compliance.get("risk_level", "unknown")
    check_mode = compliance.get("check_mode")
    color = green if comp_status == "compliant" else (yellow if comp_status == "partial" else red)
    mode_line = f"  |  模式: {check_mode}" if check_mode else ""
    print(f"  状态: {color(comp_status)}  |  风险: {color(risk)}  |  重试: {retries}/2{mode_line}")

    section("生成资料 (DocumentAgent)")
    doc_gen = final.get("document_generation", "skipped" if not docs else "completed")
    if docs:
        print(green(f"  ✓ 已生成 {len(docs)} 份资料"))
        for i, doc in enumerate(docs, 1):
            print(f"  {cyan(f'[{i}]')} {bold(doc.get('title', ''))}")
    else:
        print(yellow(f"  资料生成: {doc_gen}"))

    if history:
        section("Agent 交互时间线")
        for entry in history[-15:]:
            ts = entry.get("timestamp", "")[:19]
            print(
                f"  {dim(ts)} {cyan(entry.get('agent', '?')):<16} "
                f"{entry.get('event', ''):<18} {entry.get('summary', '')}"
            )

    print_agent_errors(result)
    print_pm_advisor(result)

    elapsed = result.get("_elapsed_ms")
    print()
    print(bold("─" * 64))
    contributed = _agents_contributed(result)
    timing = f" | 耗时={elapsed / 1000:.1f}s" if elapsed else ""
    print(
        f"  {bold('完成')} | 合规={color(comp_status)} | 资料={len(docs)} 份 | "
        f"重试={retries} 次{timing}"
    )
    if contributed:
        print(dim(f"  参与 Agent: {', '.join(contributed)}"))
    errors = result.get("agent_errors") or []
    if errors:
        print(yellow(f"  ⚠ {len(errors)} 个 Agent 异常（见上方错误详情）"))
    print(bold("─" * 64))
    print()


def print_llm_status() -> None:
    cfg = resolve_llm_config()
    if cfg is None:
        print(yellow("  LLM: 未配置 API Key — 启发式离线模式"))
        return
    print(dim(f"  LLM: {cfg.provider} / {cfg.model} (重试≤{cfg.max_retries})"))


def print_documents_full(result: dict) -> None:
    docs = result.get("generated_documents") or result.get("final_output", {}).get(
        "generated_documents", []
    )
    for doc in docs:
        section(f"{doc.get('title')} [{doc.get('doc_type')}]")
        print(doc.get("content", ""))


def print_saved_state_summary(state: dict, metadata: dict) -> None:
    section("已加载项目状态")
    print(f"  项目 ID: {state.get('project_id')}")
    print(f"  阶段: {state.get('current_phase')}")
    print(f"  保存时间: {metadata.get('saved_at', 'N/A')}")
    print(f"  上次问题: {metadata.get('last_question', 'N/A')}")
    print(f"  知识库条目: {len(state.get('knowledge_base', []))}")
    print(f"  对话记录: {len(state.get('conversation_history', []))}")
    if state.get("last_solution"):
        print(green("  ✓ 含 ProblemSolver 方案"))
    if state.get("last_pm_advice"):
        print(green("  ✓ 含 PMAdvisor 总结"))
