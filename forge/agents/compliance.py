"""ComplianceAgent — multi-standard compliance checking with structured output."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from forge.core.base_agent import BaseAgent
from forge.agents.compliance_output import (
    CheckItem,
    ComplianceOutput,
    ModuleComplianceResult,
)
from forge.agents.solution_output import SolutionOutput
from forge.core.state import WORKFLOW_PROBLEM_COMPLIANCE_LOOP, ComplianceResult, ProjectState
from forge.prompts.loader import load_prompts
from forge.utils.compliance_explain import (
    build_check_explanations,
    enrich_compliance_output,
    resolve_compliance_status_from_output,
)

_cp = load_prompts("compliance")
COMPLIANCE_REACT_TASK = _cp.COMPLIANCE_REACT_TASK
COMPLIANCE_STRUCTURED_PROMPT = _cp.COMPLIANCE_STRUCTURED_PROMPT
COMPLIANCE_SYSTEM = _cp.COMPLIANCE_SYSTEM
from forge.tools.compliance_tools import (
    build_compliance_output_from_checks,
    normalize_check_item,
    run_all_compliance_checks,
    run_compliance_research,
)
from forge.utils.agent_context import get_handoff_payload
from forge.utils.check_mode import finalize_compliance_status, resolve_check_mode
from forge.utils.conversation import record_conversation, record_thinking
from forge.utils.llm import escape_braces_for_format


class ComplianceAgent(BaseAgent):
    """
    Forge multi-standard compliance agent.

    Architecture (mirrors ProblemSolverAgent):
    1. **ReAct phase** — LLM + compliance tools investigate project evidence
    2. **Structured output** — Pydantic `ComplianceOutput`
    3. **Heuristic fallback** — deterministic checks when no API key

    Callable by ProblemSolverAgent via `validate_solution()` after方案生成.
    """

    name = "compliance"

    def _extract_context(self, state: ProjectState) -> str:
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if getattr(msg, "type", "") == "human" or msg.__class__.__name__ == "HumanMessage":
                return str(getattr(msg, "content", msg))
        return "全项目合规扫描"

    def _get_protection_level(self, state: ProjectState) -> str:
        rule_pack = state.get("rule_pack") or {}
        return str(rule_pack.get("protection_level", "3"))

    def _run_react(self, state: ProjectState, context: str) -> str:
        """Run ReAct via BaseAgent + ToolRegistry compliance tools (self.get_tools)."""
        _ = self.get_tools(state)
        task = COMPLIANCE_REACT_TASK.format(
            context=context,
            project_id=state.get("project_id", ""),
            current_phase=state.get("current_phase", ""),
            enabled_modules=", ".join(state.get("enabled_modules", [])),
            protection_level=self._get_protection_level(state),
            check_mode=resolve_check_mode(state),
        )
        return self.run_react(
            state,
            system=COMPLIANCE_SYSTEM,
            task=task,
            temperature=0.1,
            fallback=run_compliance_research(state, context),
        )

    def _build_heuristic_output(
        self,
        state: ProjectState,
        context: str = "",
        *,
        modules: list[str] | None = None,
    ) -> ComplianceOutput:
        """Build ComplianceOutput from deterministic tool checks."""
        raw = run_all_compliance_checks(state, modules=modules)
        payload = build_compliance_output_from_checks(
            raw,
            context=context,
            check_mode=resolve_check_mode(state),
        )

        results = [
            ModuleComplianceResult(
                module=mod["module"],
                module_name=mod.get("module_name", ""),
                status=mod["status"],
                score=mod["score"],
                items=[CheckItem(**item) for item in mod.get("items", [])],
                summary=mod.get("summary", ""),
            )
            for mod in payload["results"]
        ]

        base = ComplianceOutput(
            overall_status=payload["overall_status"],
            risk_level=payload["risk_level"],
            protection_level=payload.get("protection_level"),
            results=results,
            missing_items=payload["missing_items"],
            recommendations=payload["recommendations"],
            next_action=payload["next_action"],
        )
        return enrich_compliance_output(base, check_mode=resolve_check_mode(state))

    def _synthesize_structured(
        self,
        state: ProjectState,
        context: str,
        research_context: str,
    ) -> ComplianceOutput:
        """Produce ComplianceOutput via LLM structured output or heuristic builder."""
        prompt = COMPLIANCE_STRUCTURED_PROMPT.format(
            research_context=escape_braces_for_format(research_context[:12000]),
        )
        result = self.invoke_structured(
            ComplianceOutput,
            [
                SystemMessage(content=COMPLIANCE_SYSTEM),
                HumanMessage(content=f"检查上下文: {context}\n\n{prompt}"),
            ],
            temperature=0.05,
        )
        if isinstance(result, ComplianceOutput):
            return self._normalize_output(result, state)
        return self._build_heuristic_output(state, context)

    def _normalize_output(self, output: ComplianceOutput, state: ProjectState) -> ComplianceOutput:
        """Ensure rule_id on items and apply check_mode to derived compliance status."""
        check_mode = resolve_check_mode(state)
        normalized_results: list[ModuleComplianceResult] = []
        all_items: list[dict] = []

        for mod in output.results:
            items = []
            for item in mod.items:
                raw = normalize_check_item(item.model_dump())
                all_items.append(raw)
                items.append(CheckItem(**raw))
            normalized_results.append(
                ModuleComplianceResult(
                    module=mod.module,
                    module_name=mod.module_name,
                    status=mod.status,
                    score=mod.score,
                    items=items,
                    summary=mod.summary,
                )
            )

        fail_total = sum(1 for i in all_items if i.get("status") == "fail")
        warn_total = sum(1 for i in all_items if i.get("status") == "warning")
        critical_fails = sum(
            1
            for i in all_items
            if i.get("status") == "fail" and "dengbao" in i.get("category", "")
        )
        overall, risk, _ = finalize_compliance_status(
            fail_total=fail_total,
            warn_total=warn_total,
            critical_fails=critical_fails,
            check_mode=check_mode,
        )
        base = ComplianceOutput(
            overall_status=overall,
            risk_level=risk,
            protection_level=output.protection_level or self._get_protection_level(state),
            results=normalized_results,
            missing_items=output.missing_items or [],
            recommendations=output.recommendations,
            next_action=output.next_action,
        )
        return enrich_compliance_output(base, check_mode=check_mode)

    def _format_response(self, output: ComplianceOutput) -> str:
        lines = [
            "## 合规总览",
            f"- **状态**: {output.overall_status}",
            f"- **风险等级**: {output.risk_level}",
            f"- **等保级别**: {output.protection_level or 'N/A'}",
            "",
            "## 模块检查结果",
        ]
        for mod in output.results:
            lines.append(f"### {mod.module_name} ({mod.module})")
            lines.append(f"状态: {mod.status} | 得分: {mod.score}")
            lines.append(mod.summary)
            for item in mod.items:
                icon = {"pass": "✓", "fail": "✗", "warning": "!"}.get(item.status, "?")
                rid = item.rule_id or item.check_id
                lines.append(f"  {icon} rule_id={rid} | {item.title}: {item.detail}")
            lines.append("")

        if output.failed_items:
            lines.extend(["## 合规失败项 (failed_items)", ""])
            for f in output.failed_items[:10]:
                lines.append(
                    f"  ✗ `{f.rule_id}` [{f.severity}] {f.title}: {f.description[:80]}"
                )
                if f.suggestion:
                    lines.append(f"    → {f.suggestion[:120]}")
            lines.append("")

        if output.missing_items:
            lines.extend(["## 缺失项", *[f"- {m}" for m in output.missing_items], ""])
        if output.suggestions:
            lines.extend(["## 整改建议 (suggestions)", *[f"- {s}" for s in output.suggestions], ""])
        elif output.recommendations:
            lines.extend(["## 整改建议", *[f"- {r}" for r in output.recommendations], ""])
        lines.extend(["## 下一步行动", output.next_action, ""])
        lines.extend(["## 结构化输出 (JSON)", f"```json\n{output.to_display_json()}\n```"])
        return "\n".join(lines)

    def _persist_results(
        self,
        state: ProjectState,
        output: ComplianceOutput,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Build compliance_history record and compliance_results entry."""
        pack_meta = state.get("rule_pack") or {}
        checked_at = datetime.now(timezone.utc).isoformat()
        findings = output.missing_items

        legacy = ComplianceResult(
            id=f"cmp-{state['project_id']}-{len(state.get('compliance_results', []))}",
            pack_id=pack_meta.get("pack_id", "unknown"),
            modules=[r.module for r in output.results],
            status=output.overall_status,
            findings=findings,
            checked_at=checked_at,
            metadata={
                "risk_level": output.risk_level,
                "protection_level": output.protection_level,
            },
        )
        record = {
            "id": legacy.id,
            "standard": ",".join(legacy.modules),
            "rule_id": "multi_standard_scan",
            "status": legacy.status,
            "findings": legacy.findings,
            "checked_at": checked_at,
        }
        check_mode = resolve_check_mode(state)
        base_status = self._derive_compliance_status(output)
        all_items = [item.model_dump() for mod in output.results for item in mod.items]
        fail_total = sum(1 for i in all_items if i.get("status") == "fail")
        warn_total = sum(1 for i in all_items if i.get("status") == "warning")
        critical_fails = sum(
            1
            for i in all_items
            if i.get("status") == "fail" and "dengbao" in i.get("category", "")
        )
        heuristic_status = finalize_compliance_status(
            fail_total=fail_total,
            warn_total=warn_total,
            critical_fails=critical_fails,
            check_mode=check_mode,
        )[2]
        compliance_status = resolve_compliance_status_from_output(
            output, check_mode=check_mode
        )
        if check_mode == "strict" and output.failed_items:
            compliance_status = "non_compliant"
        rule_mapped = sum(
            1 for i in all_items if i.get("rule_id") or i.get("check_id")
        )
        evidence_coverage = rule_mapped / max(1, len(all_items))
        structured = {
            **output.model_dump(),
            "id": legacy.id,
            "checked_at": checked_at,
            "compliance_status": compliance_status,
            "check_mode": check_mode,
            "base_compliance_status": base_status,
            "heuristic_compliance_status": heuristic_status,
            "evidence_coverage": round(evidence_coverage, 3),
            "failed_items_count": len(output.failed_items),
        }
        structured["check_explanations"] = build_check_explanations(structured)
        return record, structured

    @staticmethod
    def _derive_compliance_status(output: ComplianceOutput) -> str:
        """Map ComplianceOutput to compliant | partial | non_compliant."""
        if output.overall_status == "pass":
            return "compliant"
        if output.overall_status == "gaps_found" and output.risk_level in ("low", "medium"):
            return "partial"
        return "non_compliant"

    def run_compliance(
        self,
        state: ProjectState,
        *,
        context: str | None = None,
        modules: list[str] | None = None,
        skip_react: bool = False,
    ) -> ComplianceOutput:
        """
        Core compliance pipeline — used by `run()` and `validate_solution()`.

        Args:
            state: Current project state
            context: Human-readable check context
            modules: Optional subset of modules to check
            skip_react: If True, skip LLM ReAct and use deterministic checks only
        """
        ctx = context or self._extract_context(state)

        if skip_react:
            research = run_compliance_research(state, ctx)
            return self._build_heuristic_output(state, ctx, modules=modules)

        research = self._run_react(state, ctx)
        return self._synthesize_structured(state, ctx, research)

    def validate_solution(
        self,
        state: ProjectState,
        solution: SolutionOutput,
        *,
        handoff: dict[str, Any] | None = None,
    ) -> ComplianceOutput:
        """
        Validate a ProblemSolver solution against compliance requirements.

        Called by ProblemSolverAgent after generating a recommended solution.
        Uses solution metadata as check context; runs deterministic checks for speed.
        """
        recommended = next(
            (s for s in solution.solutions if s.id == solution.recommended_solution_id),
            solution.solutions[0] if solution.solutions else None,
        )
        rec_title = recommended.title if recommended else "N/A"
        context = (
            f"ProblemSolver 方案合规校验 | 推荐方案: {solution.recommended_solution_id} ({rec_title}) | "
            f"{solution.problem_analysis[:300]}"
        )
        payload = handoff or {}
        if payload.get("decision_rationale"):
            context += f" | 决策依据: {str(payload['decision_rationale'])[:200]}"
        refs = payload.get("rule_pack_references") or []
        if refs:
            rule_ids = ", ".join(
                r.get("rule_id", "") for r in refs if isinstance(r, dict) and r.get("rule_id")
            )[:120]
            if rule_ids:
                context += f" | Rule Pack: {rule_ids}"
        return self.run_compliance(state, context=context, skip_react=True)

    def run(self, state: ProjectState) -> dict[str, Any]:
        """LangGraph node entrypoint — full compliance scan or solution validation."""
        in_closed_loop = state.get("active_workflow") == WORKFLOW_PROBLEM_COMPLIANCE_LOOP
        last_solution = state.get("last_solution")

        handoff = get_handoff_payload(state, self.name)
        if in_closed_loop and last_solution:
            solution = SolutionOutput.model_validate(last_solution)
            if handoff.get("rule_pack_references"):
                refs = ", ".join(
                    r.get("rule_id", "") for r in handoff["rule_pack_references"][:5]
                )
                self.logger.info("Compliance received handoff | refs=%s", refs)
            output = self.validate_solution(state, solution, handoff=handoff)
        else:
            output = self.run_compliance(state)

        record, structured = self._persist_results(state, output)

        status_label = structured.get("compliance_status", "unknown")
        if in_closed_loop:
            failed_preview = ", ".join(
                f"`{f.rule_id}`({f.severity})" for f in (output.failed_items or [])[:4]
            )
            body = (
                f"**方案合规检查**: {status_label} | 模式: {structured.get('check_mode', 'advisory')}\n"
                f"- 风险等级: {output.risk_level}\n"
                f"- failed_items: {len(output.failed_items)}"
                + (f" — {failed_preview}" if failed_preview else "")
                + f"\n- 缺口数: {len(output.missing_items)}\n"
                f"- 下一步: {output.next_action}"
            )
        else:
            body = self._format_response(output)

        self.logger.info(
            "Compliance check | status=%s risk=%s gaps=%d",
            status_label,
            output.risk_level,
            len(output.missing_items),
        )

        agent_updates: dict[str, Any] = {
            **self.reply(body),
            "last_compliance_result": structured,
            "risk_level": output.risk_level,
            "compliance_history": state.get("compliance_history", []) + [record],
            "compliance_results": state.get("compliance_results", []) + [structured],
            "workflow_step": "post_compliance" if in_closed_loop else None,
            "pending_tasks": [
                t
                for t in state.get("pending_tasks", [])
                if not (t.get("assigned_to") == self.name and t.get("status") == "open")
            ],
        }
        thinking_detail = {
            "compliance_status": status_label,
            "risk_level": output.risk_level,
            "missing_count": len(output.missing_items),
            "failed_items_count": len(output.failed_items),
            "failed_rule_ids": [f.rule_id for f in output.failed_items[:8]],
            "explanation_count": len(structured.get("check_explanations") or []),
        }
        if handoff.get("recommended_solution_id"):
            thinking_detail["validated_solution"] = handoff["recommended_solution_id"]
        if handoff.get("decision_rationale"):
            thinking_detail["decision_rationale"] = str(handoff["decision_rationale"])[:200]
        handoff_refs = handoff.get("rule_pack_references") or []
        if handoff_refs:
            thinking_detail["handoff_rule_ids"] = [
                r.get("rule_id") for r in handoff_refs if isinstance(r, dict) and r.get("rule_id")
            ][:6]
        working = {**state, **agent_updates}
        agent_updates.update(
            record_thinking(
                working,
                agent=self.name,
                thought=(
                    f"对方案 {handoff.get('recommended_solution_id', 'N/A')} 执行合规校验，"
                    f"结果 {status_label}，缺口 {len(output.missing_items)} 项"
                ),
                decision=output.next_action[:200] if output.next_action else None,
                extra=thinking_detail,
            )
        )
        working = {**state, **agent_updates}
        agent_updates.update(
            record_conversation(
                working,
                agent=self.name,
                event="compliance_check",
                summary=f"合规检查完成: {status_label}（风险 {output.risk_level}）",
                detail=thinking_detail,
            )
        )
        return agent_updates


compliance_node = ComplianceAgent()
