"""SecurityAgent — ReAct 等保2.0 security advisory."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from forge.core.base_agent import BaseAgent
from forge.agents.security_output import SecurityControlAdvice, SecurityOutput, SecurityRiskItem
from forge.core.state import ProjectState, WORKFLOW_PROBLEM_COMPLIANCE_LOOP
from forge.prompts.loader import load_prompts

_sec = load_prompts("security")
SECURITY_REACT_TASK = _sec.SECURITY_REACT_TASK
SECURITY_STRUCTURED_PROMPT = _sec.SECURITY_STRUCTURED_PROMPT
SECURITY_SYSTEM = _sec.SECURITY_SYSTEM
from forge.tools.security_tools import run_security_research
from forge.utils.conversation import record_conversation
from forge.utils.llm import escape_braces_for_format


def _mark_specialist_done(state: ProjectState, specialist: str) -> list[str]:
    done = list(state.get("specialists_completed", []))
    if specialist not in done:
        done.append(specialist)
    return done


class SecurityAgent(BaseAgent):
    """
    Forge 等保2.0 security specialist.

    Architecture:
    1. ReAct + dengbao_2.0 tools (via ToolRegistry)
    2. Structured SecurityOutput
    3. Heuristic fallback without API key
    """

    name = "security"

    def _extract_context(self, state: ProjectState) -> str:
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if getattr(msg, "type", "") == "human" or msg.__class__.__name__ == "HumanMessage":
                content = str(getattr(msg, "content", msg))
                if "【合规反馈" not in content:
                    return content
        solution = state.get("last_solution") or {}
        return solution.get("problem_analysis", "等保安全评估")

    def _get_protection_level(self, state: ProjectState) -> str:
        rule_pack = state.get("rule_pack") or {}
        return str(rule_pack.get("protection_level", "3"))

    def _run_react(self, state: ProjectState, context: str) -> str:
        _ = self.get_tools(state)
        task = SECURITY_REACT_TASK.format(
            context=context[:2000],
            project_id=state.get("project_id", ""),
            protection_level=self._get_protection_level(state),
            current_phase=state.get("current_phase", ""),
        )
        return self.run_react(
            state,
            system=SECURITY_SYSTEM,
            task=task,
            temperature=0.15,
            fallback=run_security_research(state, context),
        )

    def _build_heuristic_output(
        self,
        state: ProjectState,
        context: str,
        research_context: str,
    ) -> SecurityOutput:
        level = self._get_protection_level(state)
        compliance = state.get("last_compliance_result") or {}
        solution = state.get("last_solution") or {}
        context_lower = context.lower()

        risk_level = compliance.get("risk_level", "medium")
        if compliance.get("compliance_status") == "non_compliant":
            risk_level = "high" if risk_level not in ("critical",) else risk_level

        config_advice = [
            SecurityControlAdvice(
                control_id="db-acs-001",
                domain="access_control",
                title="身份鉴别与访问控制",
                recommendation="启用强密码策略、失败锁定与 MFA（三级及以上）",
                priority="high" if int(level) >= 3 else "medium",
            ),
            SecurityControlAdvice(
                control_id="db-aud-001",
                domain="audit",
                title="安全审计",
                recommendation="集中采集认证、授权、配置变更日志并保留 ≥6 个月",
                priority="high",
            ),
            SecurityControlAdvice(
                control_id="db-bnd-001",
                domain="firewall",
                title="边界防护",
                recommendation="默认拒绝、最小开放端口、策略变更审批",
                priority="medium",
            ),
        ]

        risks: list[SecurityRiskItem] = []
        if any(k in context_lower for k in ("401", "403", "登录", "认证")):
            risks.append(
                SecurityRiskItem(
                    title="身份鉴别失效",
                    severity="high",
                    description="认证链路异常可能导致未授权访问",
                    remediation="排查 IdP/会话/Token 策略，补齐审计证据",
                )
            )
        missing = compliance.get("missing_items", [])
        if missing:
            risks.append(
                SecurityRiskItem(
                    title="等保控制项缺口",
                    severity=risk_level if risk_level in ("low", "medium", "high", "critical") else "high",
                    description=f"存在 {len(missing)} 项缺口",
                    remediation="按 dengbao_2.0 规则逐项整改并留存测评材料",
                )
            )

        materials = [
            "安全管理制度与操作规程",
            "网络拓扑与边界防护策略说明",
            "身份鉴别与访问控制配置截图/导出",
            "安全审计日志样本与留存策略",
            "漏洞扫描与渗透测试报告（如适用）",
        ]

        diagnosis = solution.get("problem_analysis") or f"针对等保{level}级场景的安全分析：{context[:200]}"
        remediation = list(compliance.get("recommendations", []))[:5]
        if not remediation:
            remediation = [
                "对照 dengbao_2.0 控制项完成差距分析",
                "补齐防火墙/审计/访问控制三类基础证据",
            ]

        return SecurityOutput(
            diagnosis=diagnosis,
            protection_level=level,
            risk_assessment=f"当前综合风险等级评估为 {risk_level}，需优先处理身份鉴别与审计类控制项。",
            risk_level=risk_level if risk_level in ("low", "medium", "high", "critical") else "medium",
            security_risks=risks or [
                SecurityRiskItem(
                    title="待现场核实风险",
                    severity="medium",
                    description="需结合配置基线进一步确认",
                    remediation="安排安全基线核查",
                )
            ],
            remediation_items=remediation,
            configuration_advice=config_advice,
            assessment_materials=materials,
            dengbao_rule_references=["db-acs-001", "db-aud-001", "db-bnd-001"],
            recommendations=remediation,
            next_actions=[
                "完成等保差距分析表",
                "落实访问控制与审计整改",
                "准备测评访谈与证据材料",
            ],
        )

    def _synthesize_structured(
        self,
        state: ProjectState,
        context: str,
        research_context: str,
    ) -> SecurityOutput:
        prompt = SECURITY_STRUCTURED_PROMPT.format(
            context=context,
            research_context=escape_braces_for_format(research_context[:12000]),
        )
        result = self.invoke_structured(
            SecurityOutput,
            [
                SystemMessage(content=SECURITY_SYSTEM),
                HumanMessage(content=prompt),
            ],
            temperature=0.1,
        )
        if isinstance(result, SecurityOutput):
            return result
        return self._build_heuristic_output(state, context, research_context)

    def _format_response(self, output: SecurityOutput) -> str:
        lines = [
            "## 等保安全诊断",
            output.diagnosis,
            "",
            f"**保护级别**: {output.protection_level} | **风险等级**: {output.risk_level}",
            "",
            "## 风险评估",
            output.risk_assessment,
            "",
            "## 安全风险",
        ]
        for r in output.security_risks:
            lines.append(f"- **{r.title}** [{r.severity}] {r.description}")
            if r.remediation:
                lines.append(f"  - 整改: {r.remediation}")
        lines.extend(["", "## 安全配置建议"])
        for c in output.configuration_advice:
            lines.append(f"- [{c.domain}] {c.title}: {c.recommendation} ({c.priority})")
        lines.extend(["", "## 测评材料建议", *[f"- {m}" for m in output.assessment_materials]])
        lines.extend(["", "## 下一步", *[f"- {a}" for a in output.next_actions]])
        lines.extend(["", "## 结构化输出 (JSON)", f"```json\n{output.to_display_json()}\n```"])
        return "\n".join(lines)

    def run(self, state: ProjectState) -> dict[str, Any]:
        context = self._extract_context(state)
        research_context = self._run_react(state, context)
        output = self._synthesize_structured(state, context, research_context)
        output_dict = output.model_dump()

        in_loop = state.get("active_workflow") == WORKFLOW_PROBLEM_COMPLIANCE_LOOP
        suffix = "\n\n> 等保安全分析完成，将进入合规检查…" if in_loop else ""

        knowledge_entry = {
            "id": f"kb-{state['project_id']}-sec-{len(state.get('knowledge_base', []))}",
            "category": "security_advisory",
            "content": output.diagnosis,
            "source": self.name,
            "tags": ["security", "dengbao_2.0", f"level_{output.protection_level}"],
            "metadata": {"security_output": output_dict},
        }

        self.logger.info("Security advisory | level=%s risk=%s", output.protection_level, output.risk_level)

        updates: dict[str, Any] = {
            **self.reply(self._format_response(output) + suffix),
            "last_security_result": output_dict,
            "specialists_completed": _mark_specialist_done(state, "security"),
            "knowledge_base": state.get("knowledge_base", []) + [knowledge_entry],
        }
        updates.update(
            record_conversation(
                state,
                agent=self.name,
                event="security_advisory",
                summary=f"等保安全分析 | 风险={output.risk_level}",
                detail={"risk_level": output.risk_level, "protection_level": output.protection_level},
            )
        )
        return updates


security_node = SecurityAgent()
