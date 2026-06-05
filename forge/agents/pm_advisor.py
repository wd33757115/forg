"""PMAdvisorAgent — ReAct project-memory synthesis for project-manager decisions."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from forge.agents.base import BaseAgent
from forge.agents.pm_advisor_output import ActionItem, PMAdvisorOutput, RiskItem
from forge.core.state import ProjectState
from forge.prompts.pm_advisor_prompt import (
    PM_ADVISOR_REACT_TASK,
    PM_ADVISOR_STRUCTURED_PROMPT,
    PM_ADVISOR_SYSTEM,
)
from forge.tools.pm_advisor_tools import build_pm_advisor_tools, run_pm_advisor_research
from forge.utils.conversation import record_conversation
from forge.utils.llm import escape_braces_for_format, get_llm, invoke_react_agent, invoke_structured_output
from forge.utils.logger import get_logger

logger = get_logger("pm_advisor")


class PMAdvisorAgent(BaseAgent):
    """
    Project-manager advisory agent.

    Architecture:
    1. **ReAct phase** — read solution, compliance, documents, and project memory
    2. **Structured output** — Pydantic `PMAdvisorOutput`
    3. **Heuristic fallback** — rule-based PM report when no API key
    """

    name = "pm_advisor"

    def _extract_user_question(self, state: ProjectState) -> str:
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if getattr(msg, "type", "") == "human" or msg.__class__.__name__ == "HumanMessage":
                content = str(getattr(msg, "content", msg))
                if "【合规反馈" not in content:
                    return content
        return "项目执行结果汇总"

    def _run_react(self, state: ProjectState, user_question: str) -> str:
        llm = get_llm(temperature=0.2)
        if llm is None:
            return run_pm_advisor_research(state, user_question)

        tools = build_pm_advisor_tools(state)
        react_agent = create_react_agent(llm, tools)
        task = PM_ADVISOR_REACT_TASK.format(
            project_id=state.get("project_id", ""),
            current_phase=state.get("current_phase", ""),
            user_question=user_question[:2000],
        )
        try:
            result = invoke_react_agent(
                react_agent,
                {
                    "messages": [
                        SystemMessage(content=PM_ADVISOR_SYSTEM),
                        HumanMessage(content=task),
                    ]
                },
            )
        except Exception as exc:
            logger.warning("PM Advisor ReAct failed, heuristic fallback: %s", exc)
            return run_pm_advisor_research(state, user_question)
        final_messages = result.get("messages", [])
        if final_messages:
            return str(getattr(final_messages[-1], "content", final_messages[-1]))
        return run_pm_advisor_research(state, user_question)

    def _synthesize_structured(
        self,
        state: ProjectState,
        user_question: str,
        research_context: str,
    ) -> PMAdvisorOutput:
        prompt = PM_ADVISOR_STRUCTURED_PROMPT.format(
            user_question=user_question,
            research_context=escape_braces_for_format(research_context[:12000]),
        )
        result = invoke_structured_output(
            PMAdvisorOutput,
            [
                SystemMessage(content=PM_ADVISOR_SYSTEM),
                HumanMessage(content=prompt),
            ],
            temperature=0.1,
        )
        if isinstance(result, PMAdvisorOutput):
            return self._validate_output(result)
        return self._build_heuristic_output(state, user_question, research_context)

    def _priority_from_risk(self, risk_level: str) -> str:
        mapping = {
            "critical": "P0",
            "high": "P1",
            "medium": "P2",
            "low": "P3",
        }
        return mapping.get(risk_level, "P2")

    def _build_heuristic_output(
        self,
        state: ProjectState,
        user_question: str,
        research_context: str,
    ) -> PMAdvisorOutput:
        """Build PMAdvisorOutput without LLM (tests + offline mode)."""
        solution = state.get("last_solution") or {}
        compliance = state.get("last_compliance_result") or {}
        docs = state.get("generated_documents", [])
        retries = state.get("compliance_retry_count", 0)

        comp_status = compliance.get("compliance_status", compliance.get("overall_status", "unknown"))
        risk_level = compliance.get("risk_level", "medium")
        rec_id = solution.get("recommended_solution_id", "N/A")
        rec = next(
            (s for s in solution.get("solutions", []) if s.get("id") == rec_id),
            solution.get("solutions", [{}])[0] if solution.get("solutions") else {},
        )
        rec_title = rec.get("title", "待确定方案")
        missing = compliance.get("missing_items", [])
        recs = compliance.get("recommendations", [])

        summary = (
            f"针对「{user_question[:80]}」，推荐采用方案 {rec_id}（{rec_title}）。"
            f"当前合规状态为 {comp_status}，风险等级 {risk_level}。"
        )
        if docs:
            summary += f" 已生成 {len(docs)} 份项目资料可供汇报。"
        elif comp_status == "non_compliant":
            summary += f" 合规未达标（已重试 {retries} 次），需优先推进整改。"

        risks: list[RiskItem] = []
        if risk_level in ("high", "critical") or comp_status == "non_compliant":
            risks.append(
                RiskItem(
                    title="合规风险",
                    severity=risk_level if risk_level in ("low", "medium", "high", "critical") else "high",
                    impact=f"存在 {len(missing)} 项合规缺口，可能影响等保测评或验收",
                    mitigation="按整改建议补齐证据与控制项，安排专项评审",
                )
            )
        if retries >= 2 and comp_status == "non_compliant":
            risks.append(
                RiskItem(
                    title="方案迭代未达标",
                    severity="high",
                    impact="多次优化后仍不合规，可能存在架构或证据链根本缺口",
                    mitigation="召集技术+合规联合评审，必要时升级变更流程",
                )
            )

        action_items: list[ActionItem] = []
        for i, action in enumerate(solution.get("next_actions", [])[:5], 1):
            action_items.append(
                ActionItem(
                    id=f"pm-act-{i}",
                    title=action,
                    priority=self._priority_from_risk(risk_level),
                    owner="技术负责人",
                    deadline_hint="本周内" if risk_level in ("high", "critical") else "两周内",
                    rationale="来自 ProblemSolver 推荐方案的下一步行动",
                )
            )
        for i, rec in enumerate(recs[:3], len(action_items) + 1):
            action_items.append(
                ActionItem(
                    id=f"pm-act-{i}",
                    title=rec[:120],
                    priority="P1" if comp_status == "non_compliant" else "P2",
                    owner="合规接口人",
                    deadline_hint="按等保整改计划",
                    rationale="Compliance 整改建议",
                )
            )

        report_outline = [
            "1. 背景与问题描述",
            "2. 根因与影响分析",
            f"3. 推荐方案：{rec_title}",
            "4. 合规状态与风险",
            "5. 整改与实施计划",
            "6. 资源需求与里程碑",
            "7. 决策事项与下一步",
        ]
        if docs:
            report_outline.insert(5, f"5. 已生成资料清单（{len(docs)} 份）")

        return PMAdvisorOutput(
            summary=summary,
            situation_overview=solution.get("problem_analysis", "暂无详细分析")[:800],
            key_findings=solution.get("root_causes", [])[:5] or ["需进一步收集证据确认根因"],
            risks=risks,
            recommendations=recs[:5] or ["对照 Rule Pack 完成合规自查"],
            action_items=action_items,
            decision_points=[
                f"是否批准实施方案 {rec_id}（{rec_title}）",
                "是否启动等保整改专项" if comp_status != "compliant" else "是否安排回归验证",
            ],
            report_outline=report_outline,
            stakeholder_notes=(
                "向管理层汇报时突出合规风险与时间表；"
                "向客户沟通时说明已采取的措施与后续计划。"
            ),
        )

    def _validate_output(self, output: PMAdvisorOutput) -> PMAdvisorOutput:
        if not output.summary.strip():
            output.summary = "项目执行已完成，请审阅下方建议与行动项。"
        if not output.action_items:
            output.action_items = [
                ActionItem(
                    id="pm-act-1",
                    title="审阅方案与合规报告并安排评审会议",
                    priority="P2",
                    owner="项目经理",
                )
            ]
        return output

    def _format_response(self, advice: PMAdvisorOutput) -> str:
        lines = [
            "## 项目经理执行摘要",
            advice.summary,
            "",
            "## 现状概述",
            advice.situation_overview,
            "",
            "## 关键发现",
            *[f"- {f}" for f in advice.key_findings],
            "",
            "## 风险",
        ]
        for risk in advice.risks:
            lines.append(f"- **{risk.title}** [{risk.severity}] {risk.impact}")
            if risk.mitigation:
                lines.append(f"  - 缓解: {risk.mitigation}")
        lines.extend(["", "## 建议", *[f"- {r}" for r in advice.recommendations]])
        lines.extend(["", "## 行动项"])
        for item in advice.action_items:
            lines.append(
                f"- [{item.priority}] {item.title}（{item.owner}，{item.deadline_hint or '待定'}）"
            )
        lines.extend(["", "## 决策要点", *[f"- {d}" for d in advice.decision_points]])
        lines.extend(["", "## 汇报大纲", *[f"- {o}" for o in advice.report_outline]])
        if advice.stakeholder_notes:
            lines.extend(["", "## 干系人沟通", advice.stakeholder_notes])
        lines.extend(["", "## 结构化输出 (JSON)", f"```json\n{advice.to_display_json()}\n```"])
        return "\n".join(lines)

    def run(self, state: ProjectState) -> dict[str, Any]:
        user_question = self._extract_user_question(state)
        research_context = self._run_react(state, user_question)
        advice = self._synthesize_structured(state, user_question, research_context)
        advice_dict = advice.model_dump()

        knowledge_entry = {
            "id": f"kb-{state['project_id']}-pm-{len(state.get('knowledge_base', []))}",
            "category": "pm_advisory",
            "content": advice.summary,
            "source": self.name,
            "tags": ["pm_advisor", "executive_summary"],
            "metadata": {"advice": advice_dict},
        }

        logger.info(
            "PM advice generated | actions=%d risks=%d",
            len(advice.action_items),
            len(advice.risks),
        )

        agent_updates: dict[str, Any] = {
            **self.reply(self._format_response(advice)),
            "last_pm_advice": advice_dict,
            "knowledge_base": state.get("knowledge_base", []) + [knowledge_entry],
            "pending_tasks": [
                t
                for t in state.get("pending_tasks", [])
                if not (t.get("assigned_to") == self.name and t.get("status") == "open")
            ],
        }
        agent_updates.update(
            record_conversation(
                state,
                agent=self.name,
                event="pm_advice_generated",
                summary=f"PM 顾问报告：{len(advice.action_items)} 项行动，{len(advice.risks)} 项风险",
                detail={
                    "summary": advice.summary[:200],
                    "action_count": len(advice.action_items),
                    "risk_count": len(advice.risks),
                },
            )
        )
        return agent_updates


pm_advisor_node = PMAdvisorAgent()
