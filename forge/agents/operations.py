"""OperationsAgent — ReAct ITIL/ISO20000 service management advisory."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from forge.core.base_agent import BaseAgent
from forge.agents.operations_output import ChangeGuidance, IncidentGuidance, OperationsOutput
from forge.core.state import ProjectState, WORKFLOW_PROBLEM_COMPLIANCE_LOOP
from forge.prompts.loader import load_prompts

_ops = load_prompts("operations")
OPERATIONS_REACT_TASK = _ops.OPERATIONS_REACT_TASK
OPERATIONS_STRUCTURED_PROMPT = _ops.OPERATIONS_STRUCTURED_PROMPT
OPERATIONS_SYSTEM = _ops.OPERATIONS_SYSTEM
from forge.tools.operations_tools import run_operations_research
from forge.utils.conversation import record_conversation
from forge.utils.llm import escape_braces_for_format


def _mark_specialist_done(state: ProjectState, specialist: str) -> list[str]:
    done = list(state.get("specialists_completed", []))
    if specialist not in done:
        done.append(specialist)
    return done


class OperationsAgent(BaseAgent):
    """
    Forge ITIL/ISO20000 operations specialist.

    Architecture:
    1. ReAct + itil_iso20000 tools (via ToolRegistry)
    2. Structured OperationsOutput
    3. Heuristic fallback without API key
    """

    name = "operations"

    def _extract_context(self, state: ProjectState) -> str:
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if getattr(msg, "type", "") == "human" or msg.__class__.__name__ == "HumanMessage":
                content = str(getattr(msg, "content", msg))
                if "【合规反馈" not in content:
                    return content
        solution = state.get("last_solution") or {}
        return solution.get("problem_analysis", "ITIL 服务管理咨询")

    def _infer_practice_area(self, context: str) -> str:
        lower = context.lower()
        if any(k in lower for k in ("变更", "change", "cab")):
            return "change"
        if any(k in lower for k in ("问题", "根因", "problem", "rca")):
            return "problem"
        if any(k in lower for k in ("知识", "kb", "known error")):
            return "knowledge"
        if any(k in lower for k in ("事件", "incident", "故障", "中断")):
            return "incident"
        return "mixed"

    def _run_react(self, state: ProjectState, context: str) -> str:
        _ = self.get_tools(state)
        task = OPERATIONS_REACT_TASK.format(
            context=context[:2000],
            project_id=state.get("project_id", ""),
            current_phase=state.get("current_phase", ""),
        )
        return self.run_react(
            state,
            system=OPERATIONS_SYSTEM,
            task=task,
            temperature=0.15,
            fallback=run_operations_research(state, context),
        )

    def _build_heuristic_output(
        self,
        state: ProjectState,
        context: str,
        research_context: str,
    ) -> OperationsOutput:
        solution = state.get("last_solution") or {}
        practice = self._infer_practice_area(context)
        context_lower = context.lower()

        priority = "P3"
        impact = "局部服务影响"
        if any(k in context_lower for k in ("中断", "宕机", "outage", "核心")):
            priority = "P1"
            impact = "核心业务中断"
        elif any(k in context_lower for k in ("超时", "慢", "降级")):
            priority = "P2"
            impact = "性能降级"

        incident = IncidentGuidance(
            summary=f"事件处置建议：{context[:150]}",
            priority=priority,
            impact=impact,
            response_steps=[
                "记录事件时间线与影响范围",
                "分级分类并通知相关方",
                "调查诊断并实施临时规避",
                "恢复服务并验证 SLA",
                "关闭事件并触发问题管理（如需要）",
            ],
        )

        root_causes = solution.get("root_causes", [])
        if not root_causes and any(k in context_lower for k in ("根因", "rca", "问题")):
            root_causes = ["需通过日志与变更记录完成根因分析"]

        change_recs = []
        if practice in ("change", "mixed") or solution.get("recommended_solution_id"):
            change_recs.append(
                ChangeGuidance(
                    change_type="normal",
                    title="实施方案相关变更",
                    risk_level="medium",
                    approval_path=["提交 RFC", "影响评估", "CAB 审批", "变更窗口实施"],
                    rollback_plan="保留配置备份与回退脚本，验证失败 30 分钟内回滚",
                )
            )

        kb_entries = [
            f"事件记录：{context[:80]}…",
            *[f"已知错误候选：{rc}" for rc in root_causes[:2]],
        ]

        return OperationsOutput(
            practice_area=practice,
            situation_summary=solution.get("problem_analysis") or context[:300],
            incident_guidance=incident if practice in ("incident", "mixed") else None,
            root_cause_analysis=root_causes,
            change_recommendations=change_recs,
            knowledge_base_entries=kb_entries,
            sla_considerations=(
                f"建议按 {priority} 级别响应；P1 需立即升级服务负责人并同步客户。"
            ),
            itil_rule_references=["itil-inc-001", "itil-prb-001", "itil-chg-001"],
            recommendations=[
                "按事件管理流程记录完整时间线",
                "对重复性问题启动问题管理与根因分析",
                "重大修复通过变更管理实施",
            ],
            next_actions=[
                "更新事件单状态与沟通记录",
                "安排根因分析会议（如 P1/P2）",
                "沉淀知识库条目",
            ],
        )

    def _synthesize_structured(
        self,
        state: ProjectState,
        context: str,
        research_context: str,
    ) -> OperationsOutput:
        prompt = OPERATIONS_STRUCTURED_PROMPT.format(
            context=context,
            research_context=escape_braces_for_format(research_context[:12000]),
        )
        result = self.invoke_structured(
            OperationsOutput,
            [
                SystemMessage(content=OPERATIONS_SYSTEM),
                HumanMessage(content=prompt),
            ],
            temperature=0.1,
        )
        if isinstance(result, OperationsOutput):
            return result
        return self._build_heuristic_output(state, context, research_context)

    def _format_response(self, output: OperationsOutput) -> str:
        lines = [
            "## ITIL 运维分析",
            output.situation_summary,
            "",
            f"**实践域**: {output.practice_area}",
            "",
        ]
        if output.incident_guidance:
            ig = output.incident_guidance
            lines.extend(
                [
                    "## 事件管理",
                    f"优先级: {ig.priority} | 影响: {ig.impact}",
                    ig.summary,
                    "",
                    "### 响应步骤",
                    *[f"- {s}" for s in ig.response_steps],
                    "",
                ]
            )
        if output.root_cause_analysis:
            lines.extend(["## 根因分析", *[f"- {r}" for r in output.root_cause_analysis], ""])
        if output.change_recommendations:
            lines.append("## 变更建议")
            for ch in output.change_recommendations:
                lines.append(f"- [{ch.change_type}] {ch.title} (风险: {ch.risk_level})")
                lines.append(f"  审批: {' → '.join(ch.approval_path)}")
        lines.extend(["", "## SLA 考量", output.sla_considerations])
        lines.extend(["", "## 知识库沉淀", *[f"- {k}" for k in output.knowledge_base_entries]])
        lines.extend(["", "## 下一步", *[f"- {a}" for a in output.next_actions]])
        lines.extend(["", "## 结构化输出 (JSON)", f"```json\n{output.to_display_json()}\n```"])
        return "\n".join(lines)

    def run(self, state: ProjectState) -> dict[str, Any]:
        context = self._extract_context(state)
        research_context = self._run_react(state, context)
        output = self._synthesize_structured(state, context, research_context)
        output_dict = output.model_dump()

        in_loop = state.get("active_workflow") == WORKFLOW_PROBLEM_COMPLIANCE_LOOP
        suffix = "\n\n> ITIL 运维分析完成，将进入合规检查…" if in_loop else ""

        knowledge_entry = {
            "id": f"kb-{state['project_id']}-ops-{len(state.get('knowledge_base', []))}",
            "category": "operations_advisory",
            "content": output.situation_summary,
            "source": self.name,
            "tags": ["operations", "itil_iso20000", output.practice_area],
            "metadata": {"operations_output": output_dict},
        }

        self.logger.info("Operations advisory | practice=%s", output.practice_area)

        updates: dict[str, Any] = {
            **self.reply(self._format_response(output) + suffix),
            "last_operations_result": output_dict,
            "specialists_completed": _mark_specialist_done(state, "operations"),
            "knowledge_base": state.get("knowledge_base", []) + [knowledge_entry],
        }
        updates.update(
            record_conversation(
                state,
                agent=self.name,
                event="operations_advisory",
                summary=f"ITIL 运维分析 | 域={output.practice_area}",
                detail={"practice_area": output.practice_area},
            )
        )
        return updates


operations_node = OperationsAgent()
