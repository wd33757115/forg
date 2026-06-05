"""ProblemSolverAgent — ReAct investigation + structured solution output."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from forge.core.base_agent import BaseAgent
from forge.agents.problem_classifier import (
    PROBLEM_TYPE_LABELS,
    ProblemType,
    classify_problem,
    modules_for_problem_type,
)
from forge.agents.rule_pack_refs import fetch_relevant_rules
from forge.agents.solution_output import RulePackReference, SolutionOption, SolutionOutput
from forge.core.state import WORKFLOW_PROBLEM_COMPLIANCE_LOOP, ProjectState
from forge.prompts.problem_solver_prompt import (
    PROBLEM_SOLVER_REACT_TASK,
    PROBLEM_SOLVER_STRUCTURED_PROMPT,
    PROBLEM_SOLVER_SYSTEM,
)
from forge.tools.problem_solver_tools import run_tool_research
from forge.utils.agent_context import build_handoff
from forge.utils.conversation import record_conversation, record_thinking
from forge.utils.knowledge import format_knowledge_context, search_knowledge
from forge.utils.llm import escape_braces_for_format


class ProblemSolverAgent(BaseAgent):
    """
    Forge core problem-solving agent.

    Architecture:
    1. **Classify** — security / service_management / technical / mixed
    2. **ReAct phase** — LLM + tools investigate Rule Pack, 等保, ITIL
    3. **Structured output** — Pydantic SolutionOutput with rule_pack_references
    4. **Handoff** — structured context for Compliance / Security / Operations
    """

    name = "problem_solver"

    def _extract_problem_statement(self, state: ProjectState) -> str:
        messages = state.get("messages", [])
        parts: list[str] = []
        for msg in reversed(messages):
            if getattr(msg, "type", "") == "human" or msg.__class__.__name__ == "HumanMessage":
                content = str(getattr(msg, "content", msg))
                parts.append(content)
                if "【合规反馈" not in content:
                    break
        return "\n\n".join(reversed(parts)) if parts else ""

    def _classify(self, state: ProjectState, problem_statement: str) -> tuple[ProblemType, str]:
        hint = state.get("problem_type") or state.get("problem_type_hint")
        return classify_problem(problem_statement, hint=hint)

    def _run_react(
        self,
        state: ProjectState,
        problem_statement: str,
        problem_type: ProblemType,
        type_reason: str,
    ) -> str:
        """Run ReAct via BaseAgent helper + ToolRegistry tools."""
        priority_modules = ", ".join(modules_for_problem_type(problem_type))
        fallback = run_tool_research(
            state, problem_statement, problem_type=problem_type
        )
        prior = search_knowledge(state, tags=[problem_type], limit=3)
        prior_cases = format_knowledge_context(prior)
        task = PROBLEM_SOLVER_REACT_TASK.format(
            problem_statement=problem_statement,
            problem_type=problem_type,
            type_reason=type_reason,
            priority_modules=priority_modules,
            project_id=state.get("project_id", ""),
            current_phase=state.get("current_phase", ""),
            enabled_modules=", ".join(state.get("enabled_modules", [])),
            prior_cases=prior_cases,
        )
        return self.run_react(
            state,
            system=PROBLEM_SOLVER_SYSTEM,
            task=task,
            temperature=0.2,
            fallback=fallback,
        )

    def _synthesize_structured(
        self,
        state: ProjectState,
        problem_statement: str,
        research_context: str,
        problem_type: ProblemType,
        type_reason: str,
    ) -> SolutionOutput:
        """Produce validated SolutionOutput via LLM structured output or heuristic builder."""
        prompt = PROBLEM_SOLVER_STRUCTURED_PROMPT.format(
            problem_statement=problem_statement,
            problem_type=problem_type,
            type_reason=type_reason,
            research_context=escape_braces_for_format(research_context[:12000]),
        )
        result = self.invoke_structured(
            SolutionOutput,
            [
                SystemMessage(content=PROBLEM_SOLVER_SYSTEM),
                HumanMessage(content=prompt),
            ],
            temperature=0.1,
        )
        if isinstance(result, SolutionOutput):
            result.problem_type = result.problem_type or problem_type
            return self._validate_solution_output(
                result,
                problem_statement=problem_statement,
                problem_type=problem_type,
            )

        return self._build_heuristic_solution(
            state, problem_statement, research_context, problem_type, type_reason
        )

    def _build_heuristic_solution(
        self,
        state: ProjectState,
        problem_statement: str,
        research_context: str,
        problem_type: ProblemType,
        type_reason: str,
    ) -> SolutionOutput:
        """Build a valid SolutionOutput without LLM (tests + offline mode)."""
        rule_refs = fetch_relevant_rules(problem_type, problem_statement)
        problem_lower = problem_statement.lower()

        is_auth = any(k in problem_lower for k in ("401", "403", "登录", "认证", "auth"))
        is_perf = any(k in problem_lower for k in ("慢", "超时", "timeout", "latency"))
        is_itil_evt = any(k in problem_lower for k in ("事件", "中断", "宕机", "itil", "sla"))

        if problem_type == "security" or is_auth:
            analysis = (
                f"【{PROBLEM_TYPE_LABELS.get(problem_type, problem_type)}】"
                "认证/授权或等保控制项相关故障，需对照身份鉴别与访问控制条款整改。"
            )
            root_causes = [
                "SSO/LDAP 证书过期或配置漂移（关联 db-acs-001）",
                "角色映射与最小权限策略不一致",
                "变更未走 ITIL 变更管理（itil-chg-001）",
            ]
            solutions = [
                SolutionOption(
                    id="sol-a",
                    title="紧急恢复：证书与配置回滚",
                    description="验证 IdP 证书，回滚近期认证配置变更",
                    approach="检查 SSO 证书 → 同步节点 → 验证登录链路",
                    trade_offs=["恢复快但可能未解决根因"],
                    compliance_impact="临时满足 db-acs-001 身份鉴别，需补充变更记录",
                    itil_guidance="itil-inc-001 记录事件并分级响应",
                    estimated_effort="low",
                    risk_level="low",
                ),
                SolutionOption(
                    id="sol-b",
                    title="根治：身份治理与审计加固",
                    description="重建 RBAC 基线，集中认证审计",
                    approach="RBAC 审计 → 角色映射修复 → 启用审计集中采集",
                    trade_offs=["周期较长", "需多团队协同"],
                    compliance_impact="对齐 db-acs-001、db-aud-001 控制项",
                    itil_guidance="itil-prb-001 根因分析 + itil-chg-001 变更实施",
                    estimated_effort="high",
                    risk_level="medium",
                ),
            ]
            recommended = "sol-a"
            dengbao = [f"核查 {r.rule_id} {r.title}" for r in rule_refs if r.module == "dengbao_2.0"][:4]
            itil = [f"执行 {r.rule_id} 相关要求" for r in rule_refs if r.module == "itil_iso20000"][:3]
        elif problem_type == "service_management" or is_itil_evt:
            analysis = (
                f"【{PROBLEM_TYPE_LABELS.get(problem_type, problem_type)}】"
                "ITIL 服务管理场景：需按事件管理流程恢复服务并评估 SLA 影响。"
            )
            root_causes = ["核心组件故障导致服务中断", "变更窗口内未验证回退方案", "CMDB 配置项与实际不一致"]
            solutions = [
                SolutionOption(
                    id="sol-a",
                    title="事件响应：恢复服务优先",
                    description="按 P1 事件流程恢复业务并记录时间线",
                    approach="记录事件 → 分级 → 临时规避 → 验证 SLA",
                    trade_offs=["可能未根治"],
                    compliance_impact="确保调查过程保留审计证据（db-aud-001）",
                    itil_guidance="itil-inc-001 / itil-inc-002 重大事件升级",
                    estimated_effort="low",
                    risk_level="medium",
                ),
                SolutionOption(
                    id="sol-b",
                    title="问题管理：根因与变更闭环",
                    description="启动问题管理，通过 CAB 实施永久修复",
                    approach="RCA → 已知错误 → RFC → CAB → 发布",
                    trade_offs=["周期长", "根治彻底"],
                    compliance_impact="变更记录满足 si-chg-001",
                    itil_guidance="itil-prb-001 + itil-chg-002 CAB 评审",
                    estimated_effort="high",
                    risk_level="low",
                ),
            ]
            recommended = "sol-a"
            dengbao = ["确认事件处置不破坏等保审计连续性"]
            itil = [f"对齐 {r.rule_id}: {r.title}" for r in rule_refs if r.module == "itil_iso20000"][:4]
        elif is_perf or problem_type == "technical":
            analysis = f"【技术类】性能或集成链路问题：{type_reason}"
            root_causes = ["数据库连接池耗尽", "跨系统调用超时", "近期变更引入性能回归"]
            solutions = [
                SolutionOption(
                    id="sol-a",
                    title="快速缓解：限流与扩容",
                    description="临时扩容并启用限流",
                    approach="定位瓶颈 → 扩容/限流 → 验证 SLA",
                    trade_offs=["临时方案"],
                    compliance_impact="确保 db-aud-001 审计日志不丢失",
                    itil_guidance="itil-inc-001 事件恢复 + itil-slm-001 SLA 评估",
                    estimated_effort="low",
                    risk_level="low",
                ),
                SolutionOption(
                    id="sol-b",
                    title="架构优化：链路治理",
                    description="优化集成调用链，容量规划",
                    approach="全链路追踪 → 热点优化 → 容量规划",
                    trade_offs=["开发周期长"],
                    compliance_impact="变更走 si-chg-001 / itil-chg-001",
                    itil_guidance="itil-cap-001 容量管理",
                    estimated_effort="high",
                    risk_level="medium",
                ),
            ]
            recommended = "sol-a"
            dengbao = ["确保安全审计持续可用"]
            itil = ["对照 SLA 评估服务影响"]
        else:
            analysis = f"【混合场景】{problem_statement[:200]} — {type_reason}"
            root_causes = ["安全控制与服务可用性交叉影响", "需联合安全与运维团队诊断"]
            solutions = [
                SolutionOption(
                    id="sol-a",
                    title="联合应急：安全加固 + 服务恢复",
                    description="并行处理认证故障与基础设施中断",
                    approach="安全组隔离风险 → 运维恢复链路 → 联合验证",
                    trade_offs=["协调成本高"],
                    compliance_impact="满足 db-acs-001 同时记录 itil-inc-001 事件",
                    itil_guidance="P1 事件升级 + 安全事件应急预案",
                    estimated_effort="medium",
                    risk_level="high",
                ),
                SolutionOption(
                    id="sol-b",
                    title="体系化整改：等保 + ITIL 双轨",
                    description="按 Rule Pack 双模块差距分析后分阶段整改",
                    approach="差距分析 → 分轨整改 → 联合验收",
                    trade_offs=["周期长", "长期收益大"],
                    compliance_impact="覆盖 dengbao_2.0 + itil_iso20000 关键条款",
                    itil_guidance="变更管理与发布管理联动",
                    estimated_effort="high",
                    risk_level="medium",
                ),
            ]
            recommended = "sol-a"
            dengbao = [f"{r.rule_id}: {r.title}" for r in rule_refs if "db-" in r.rule_id][:3]
            itil = [f"{r.rule_id}: {r.title}" for r in rule_refs if "itil-" in r.rule_id][:3]

        if "severity_hint" in research_context and "high" in research_context:
            for sol in solutions:
                if sol.id == recommended:
                    sol.risk_level = "high"

        return SolutionOutput(
            problem_type=problem_type,
            problem_analysis=analysis,
            root_causes=root_causes,
            rule_pack_references=rule_refs,
            solutions=solutions,
            recommended_solution_id=recommended,
            next_actions=[
                f"确认影响范围（项目 {state.get('project_id', 'N/A')}）",
                f"执行推荐方案 {recommended}",
                "更新知识库并关联 Rule Pack rule_id",
                "如需变更，提交 ITIL RFC（itil-chg-001）",
            ],
            dengbao_considerations=dengbao or ["对照等保控制项验证"],
            itil_considerations=itil or ["按事件管理流程记录"],
        )

    def _validate_solution_output(
        self,
        output: SolutionOutput,
        *,
        problem_statement: str = "",
        problem_type: ProblemType | None = None,
    ) -> SolutionOutput:
        """Ensure recommended_solution_id references an existing solution."""
        valid_ids = {s.id for s in output.solutions}
        if output.recommended_solution_id not in valid_ids and output.solutions:
            output.recommended_solution_id = output.solutions[0].id
        if len(output.solutions) < 2:
            output.solutions.append(
                SolutionOption(
                    id="sol-fallback",
                    title="保守观察方案",
                    description="持续监控并收集更多证据后再决策",
                    approach="加强监控 → 每日复盘",
                    trade_offs=["延迟解决"],
                    compliance_impact="维持现有合规状态",
                    itil_guidance="Incident Monitoring",
                    estimated_effort="low",
                    risk_level="low",
                )
            )
        if not output.rule_pack_references:
            ptype = problem_type or output.problem_type
            if ptype:
                output.rule_pack_references = fetch_relevant_rules(
                    ptype,
                    problem_statement or output.problem_analysis,
                )
        return output

    def _format_response(self, solution: SolutionOutput) -> str:
        """Human-readable response with embedded JSON block."""
        recommended = next(
            (s for s in solution.solutions if s.id == solution.recommended_solution_id),
            solution.solutions[0] if solution.solutions else None,
        )
        rec_title = recommended.title if recommended else "N/A"

        lines = [
            f"## 问题类型: {solution.problem_type}",
            "",
            "## 问题分析",
            solution.problem_analysis,
            "",
            "## Rule Pack 引用",
        ]
        for ref in solution.rule_pack_references[:6]:
            lines.append(f"- [{ref.rule_id}] {ref.title} ({ref.module})")
        lines.extend(["", "## 根因", *[f"- {rc}" for rc in solution.root_causes], ""])
        lines.extend(["## 推荐方案", f"**{solution.recommended_solution_id}**: {rec_title}", ""])
        for sol in solution.solutions:
            marker = " ← 推荐" if sol.id == solution.recommended_solution_id else ""
            lines.append(f"### [{sol.id}] {sol.title}{marker}")
            lines.append(sol.description)
            lines.append(f"- 等保: {sol.compliance_impact}")
            lines.append(f"- ITIL: {sol.itil_guidance}")
            lines.append("")
        lines.extend(["## 下一步行动", *[f"- {a}" for a in solution.next_actions]])
        lines.extend(["", "## 结构化输出 (JSON)", f"```json\n{solution.to_display_json()}\n```"])
        return "\n".join(lines)

    def run(self, state: ProjectState) -> dict[str, Any]:
        problem_statement = self._extract_problem_statement(state)
        if not problem_statement:
            problem_statement = "未提供具体问题描述，请分析当前项目风险与待办。"

        problem_type, type_reason = self._classify(state, problem_statement)
        self.logger.info("Problem classified | type=%s reason=%s", problem_type, type_reason)

        research_context = self._run_react(state, problem_statement, problem_type, type_reason)
        solution = self._synthesize_structured(
            state, problem_statement, research_context, problem_type, type_reason
        )

        retry_count = state.get("compliance_retry_count", 0)
        if retry_count > 0 and state.get("last_compliance_result"):
            compliance = state["last_compliance_result"]
            solution.problem_analysis += (
                f"\n\n[重试 #{retry_count}] 已根据合规反馈优化，"
                f"针对 {len(compliance.get('missing_items', []))} 项缺口调整。"
            )

        solution_dict = solution.model_dump()
        in_closed_loop = state.get("active_workflow") == WORKFLOW_PROBLEM_COMPLIANCE_LOOP
        recommended = next(
            (s for s in solution.solutions if s.id == solution.recommended_solution_id),
            solution.solutions[0] if solution.solutions else None,
        )

        handoff_payload = {
            "problem_type": problem_type,
            "problem_statement": problem_statement[:2000],
            "recommended_solution_id": solution.recommended_solution_id,
            "recommended_solution": recommended.model_dump() if recommended else {},
            "rule_pack_references": [r.model_dump() for r in solution.rule_pack_references],
            "root_causes": solution.root_causes,
            "dengbao_considerations": solution.dengbao_considerations,
            "itil_considerations": solution.itil_considerations,
        }

        knowledge_entry = {
            "id": f"kb-{state['project_id']}-ps-{len(state.get('knowledge_base', []))}",
            "category": "problem_solution",
            "content": solution.problem_analysis,
            "source": self.name,
            "tags": ["problem_solver", problem_type, f"attempt_{retry_count + 1}"],
            "metadata": {
                "solution": solution_dict,
                "recommended_solution_id": solution.recommended_solution_id,
                "retry_count": retry_count,
                "problem_type": problem_type,
            },
        }

        response_body = self._format_response(solution)
        if in_closed_loop:
            response_body += (
                f"\n\n> 方案已生成（第 {retry_count + 1} 次），"
                "结构化上下文已传递给 ComplianceAgent…"
            )

        attempt = retry_count + 1
        self.logger.info(
            "Solution generated | id=%s type=%s attempt=%d",
            solution.recommended_solution_id,
            problem_type,
            attempt,
        )

        agent_updates: dict[str, Any] = {
            **self.reply(response_body),
            "last_solution": solution_dict,
            "problem_type": problem_type,
            "knowledge_base": state.get("knowledge_base", []) + [knowledge_entry],
            "pending_tasks": [
                t
                for t in state.get("pending_tasks", [])
                if not (t.get("assigned_to") == self.name and t.get("status") == "open")
            ],
        }
        agent_updates.update(
            build_handoff(
                {**state, **agent_updates},
                from_agent=self.name,
                to_agent="compliance",
                payload=handoff_payload,
            )
        )
        agent_updates.update(
            record_thinking(
                state,
                agent=self.name,
                thought=f"判定问题类型为 {problem_type}（{type_reason}）",
                decision=f"推荐方案 {solution.recommended_solution_id}",
                evidence=[r.rule_id for r in solution.rule_pack_references[:5]],
                extra={"problem_type": problem_type, "attempt": attempt},
            )
        )
        agent_updates.update(
            record_conversation(
                state,
                agent=self.name,
                event="solution_generated",
                summary=f"[{problem_type}] 方案 {solution.recommended_solution_id}（第 {attempt} 次）",
                detail={
                    "problem_type": problem_type,
                    "recommended_solution_id": solution.recommended_solution_id,
                    "rule_pack_refs": [r.rule_id for r in solution.rule_pack_references],
                    "attempt": attempt,
                },
            )
        )
        return agent_updates


problem_solver_node = ProblemSolverAgent()
