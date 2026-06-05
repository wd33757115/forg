"""ProblemSolverAgent — ReAct investigation + structured solution output."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from forge.agents.base import BaseAgent
from forge.agents.solution_output import SolutionOption, SolutionOutput
from forge.core.state import ProjectState
from forge.prompts.problem_solver_prompt import (
    PROBLEM_SOLVER_REACT_TASK,
    PROBLEM_SOLVER_STRUCTURED_PROMPT,
    PROBLEM_SOLVER_SYSTEM,
)
from forge.tools.problem_solver_tools import build_problem_solver_tools, run_tool_research
from forge.utils.llm import get_llm


class ProblemSolverAgent(BaseAgent):
    """
    Forge core problem-solving agent.

    Architecture:
    1. **ReAct phase** — LLM + tools investigate project context, Rule Pack, 等保, ITIL
    2. **Structured output phase** — Pydantic `SolutionOutput` via `with_structured_output`
    3. **Heuristic fallback** — rule-based `SolutionOutput` when no API key is available
    """

    name = "problem_solver"

    def _extract_problem_statement(self, state: ProjectState) -> str:
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if getattr(msg, "type", "") == "human" or msg.__class__.__name__ == "HumanMessage":
                return str(getattr(msg, "content", msg))
        return ""

    def _run_react(self, state: ProjectState, problem_statement: str) -> str:
        """Run LangGraph ReAct agent with project-bound tools."""
        llm = get_llm(temperature=0.2)
        if llm is None:
            return run_tool_research(state, problem_statement)

        tools = build_problem_solver_tools(state)
        react_agent = create_react_agent(llm, tools)

        task = PROBLEM_SOLVER_REACT_TASK.format(
            problem_statement=problem_statement,
            project_id=state.get("project_id", ""),
            current_phase=state.get("current_phase", ""),
            enabled_modules=", ".join(state.get("enabled_modules", [])),
        )

        result = react_agent.invoke(
            {
                "messages": [
                    SystemMessage(content=PROBLEM_SOLVER_SYSTEM),
                    HumanMessage(content=task),
                ]
            }
        )

        final_messages = result.get("messages", [])
        if final_messages:
            return str(getattr(final_messages[-1], "content", final_messages[-1]))
        return run_tool_research(state, problem_statement)

    def _synthesize_structured(
        self,
        state: ProjectState,
        problem_statement: str,
        research_context: str,
    ) -> SolutionOutput:
        """Produce validated SolutionOutput via LLM structured output or heuristic builder."""
        llm = get_llm(temperature=0.1)
        if llm is not None:
            try:
                structured_llm = llm.with_structured_output(SolutionOutput)
                prompt = PROBLEM_SOLVER_STRUCTURED_PROMPT.format(
                    problem_statement=problem_statement,
                    research_context=research_context[:12000],
                )
                result = structured_llm.invoke(
                    [
                        SystemMessage(content=PROBLEM_SOLVER_SYSTEM),
                        HumanMessage(content=prompt),
                    ]
                )
                if isinstance(result, SolutionOutput):
                    return self._validate_solution_output(result)
            except Exception:
                pass  # fall through to heuristic

        return self._build_heuristic_solution(state, problem_statement, research_context)

    def _build_heuristic_solution(
        self,
        state: ProjectState,
        problem_statement: str,
        research_context: str,
    ) -> SolutionOutput:
        """Build a valid SolutionOutput without LLM (tests + offline mode)."""
        problem_lower = problem_statement.lower()

        # Infer problem type from keywords
        is_auth = any(k in problem_lower for k in ("401", "403", "登录", "认证", "auth"))
        is_perf = any(k in problem_lower for k in ("慢", "超时", "timeout", "latency"))
        is_compliance = any(k in problem_lower for k in ("等保", "合规", "审计"))

        if is_auth:
            analysis = "认证/授权故障：身份集成或策略同步异常，可能影响等保身份鉴别与访问控制项。"
            root_causes = [
                "SSO/LDAP 证书过期或配置漂移",
                "角色映射与等保最小权限策略不一致",
                "集成接口 Token 校验逻辑变更未走变更管理",
            ]
            solutions = [
                SolutionOption(
                    id="sol-a",
                    title="紧急恢复：证书与配置回滚",
                    description="验证 IdP 证书有效期，回滚近期认证配置变更",
                    approach="检查 SSO 证书 → 同步至所有节点 → 验证登录链路",
                    trade_offs=["恢复快但可能未解决根因", "需要变更窗口"],
                    compliance_impact="满足 GB/T 22239 身份鉴别临时恢复，需补充变更记录",
                    itil_guidance="按 Incident Management 记录事件并关联 Problem 记录",
                    estimated_effort="low",
                    risk_level="low",
                ),
                SolutionOption(
                    id="sol-b",
                    title="根治：统一身份治理与审计加固",
                    description="重建角色映射基线，启用集中认证审计",
                    approach="RBAC 审计 → 角色映射修复 → 启用认证日志集中采集",
                    trade_offs=["周期较长", "需多团队协同"],
                    compliance_impact="对齐等保2.0 身份鉴别、访问控制、安全审计控制项",
                    itil_guidance="Problem Management 根因分析 + Change Enablement 实施",
                    estimated_effort="high",
                    risk_level="medium",
                ),
            ]
            recommended = "sol-a"
            dengbao = ["核查身份鉴别唯一性与失败处理（db-acs-001）", "确认访问控制策略同步（db-acs-001）"]
            itil = ["记录 ITIL 事件并分级", "若复发则启动问题管理流程（itil-prb-001）"]
        elif is_perf:
            analysis = "性能劣化：集成链路延迟或资源瓶颈，需结合 WBS 与 SLA 评估影响。"
            root_causes = ["数据库连接池耗尽", "跨系统调用链路超时", "近期变更引入性能回归"]
            solutions = [
                SolutionOption(
                    id="sol-a",
                    title="快速缓解：限流与扩容",
                    description="临时扩容资源并启用限流保护",
                    approach="监控定位瓶颈 → 扩容/限流 → 验证 SLA",
                    trade_offs=["临时方案", "成本增加"],
                    compliance_impact="需确保审计日志不因限流丢失",
                    itil_guidance="Incident Management 优先恢复服务",
                    estimated_effort="low",
                    risk_level="low",
                ),
                SolutionOption(
                    id="sol-b",
                    title="架构优化：链路治理",
                    description="优化集成调用链，增加缓存与异步",
                    approach="全链路追踪 → 热点优化 → 容量规划",
                    trade_offs=["开发周期较长", "需架构评审"],
                    compliance_impact="变更需走变更管理并更新配置基线（itil-cfg-001）",
                    itil_guidance="Change Enablement + Capacity Management",
                    estimated_effort="high",
                    risk_level="medium",
                ),
            ]
            recommended = "sol-a"
            dengbao = ["确保安全审计持续可用（db-aud-001）"]
            itil = ["对照 SLA 评估服务影响（itil-slm-001）"]
        elif is_compliance:
            analysis = "合规缺口：等保控制项证据不足或流程未对齐，需整改与证据补齐。"
            root_causes = ["安全管理制度未更新", "审计日志保留策略不满足要求", "边界防护策略未文档化"]
            solutions = [
                SolutionOption(
                    id="sol-a",
                    title="证据补齐冲刺",
                    description="按 Rule Pack 缺口清单逐项补齐文档与日志证据",
                    approach="差距清单 → 责任分配 → 证据采集 → 复核",
                    trade_offs=["工作量大", "见效快"],
                    compliance_impact="直接对齐 dengbao_2.0 Rule Pack 检查项",
                    itil_guidance="纳入变更管理确保整改可追溯",
                    estimated_effort="medium",
                    risk_level="low",
                ),
                SolutionOption(
                    id="sol-b",
                    title="合规内建（Compliance by Design）",
                    description="将等保控制项嵌入实施与运维流程",
                    approach="控制项映射 WBS → 自动化检查 → 持续监控",
                    trade_offs=["前期投入高", "长期收益大"],
                    compliance_impact="全面覆盖等保技术与管理层要求",
                    itil_guidance="与 Service Configuration Management 联动",
                    estimated_effort="high",
                    risk_level="medium",
                ),
            ]
            recommended = "sol-a"
            dengbao = ["对照等保三级要求逐项验证（get_dengbao_requirements）"]
            itil = ["整改纳入变更管理（itil-chg-001）"]
        else:
            analysis = f"待深入分析问题：{problem_statement[:200]}"
            root_causes = ["信息不足，需补充日志与时间线", "影响范围未完全确认"]
            solutions = [
                SolutionOption(
                    id="sol-a",
                    title="信息收集与初步隔离",
                    description="收集证据、划定影响范围、必要时隔离故障组件",
                    approach="时间线梳理 → 日志采集 → 影响评估",
                    trade_offs=["延迟根治", "风险可控"],
                    compliance_impact="确保调查过程不破坏审计证据",
                    itil_guidance="Incident Management 标准流程",
                    estimated_effort="low",
                    risk_level="low",
                ),
                SolutionOption(
                    id="sol-b",
                    title="联合诊断工作坊",
                    description="组织跨团队根因分析会议",
                    approach="邀请集成/安全/运维 → 联合诊断 → 输出 RCA 报告",
                    trade_offs=["协调成本高", "结论更可靠"],
                    compliance_impact="输出物可作为等保运维管理证据",
                    itil_guidance="Problem Management 根因分析",
                    estimated_effort="medium",
                    risk_level="low",
                ),
            ]
            recommended = "sol-a"
            dengbao = ["确认问题是否触及等保控制项"]
            itil = ["按事件管理流程记录与分级"]

        # Enrich from research context if impact data present
        if "severity_hint" in research_context and "high" in research_context:
            for sol in solutions:
                if sol.id == recommended:
                    sol.risk_level = "high"

        next_actions = [
            f"确认问题影响范围（项目 {state.get('project_id', 'N/A')}，阶段 {state.get('current_phase', 'N/A')}）",
            f"执行推荐方案 {recommended} 的第一步行动",
            "更新项目知识库并关联 Rule Pack 规则 ID",
            "如需变更，提交 ITIL 变更请求",
        ]

        return SolutionOutput(
            problem_analysis=analysis,
            root_causes=root_causes,
            solutions=solutions,
            recommended_solution_id=recommended,
            next_actions=next_actions,
            dengbao_considerations=dengbao,
            itil_considerations=itil,
        )

    def _validate_solution_output(self, output: SolutionOutput) -> SolutionOutput:
        """Ensure recommended_solution_id references an existing solution."""
        valid_ids = {s.id for s in output.solutions}
        if output.recommended_solution_id not in valid_ids and output.solutions:
            output.recommended_solution_id = output.solutions[0].id
        if len(output.solutions) < 2:
            # Pad with a conservative fallback option
            output.solutions.append(
                SolutionOption(
                    id="sol-fallback",
                    title="保守观察方案",
                    description="持续监控并收集更多证据后再决策",
                    approach="加强监控 → 每日复盘 → 证据充分后行动",
                    trade_offs=["延迟解决"],
                    compliance_impact="维持现有合规状态",
                    itil_guidance="Incident Monitoring",
                    estimated_effort="low",
                    risk_level="low",
                )
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
            "## 问题分析",
            solution.problem_analysis,
            "",
            "## 根因",
            *[f"- {rc}" for rc in solution.root_causes],
            "",
            "## 推荐方案",
            f"**{solution.recommended_solution_id}**: {rec_title}",
            "",
            "## 方案选项",
        ]
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

        # Phase 1: ReAct tool investigation
        research_context = self._run_react(state, problem_statement)

        # Phase 2: Structured output synthesis
        solution = self._synthesize_structured(state, problem_statement, research_context)

        knowledge_entry = {
            "id": f"kb-{state['project_id']}-ps-{len(state.get('knowledge_base', []))}",
            "category": "problem_solution",
            "content": solution.problem_analysis,
            "source": self.name,
            "tags": ["problem_solver", "structured_output"],
            "metadata": {
                "solution": solution.model_dump(),
                "recommended_solution_id": solution.recommended_solution_id,
            },
        }

        return {
            **self.reply(self._format_response(solution)),
            "knowledge_base": state.get("knowledge_base", []) + [knowledge_entry],
            "pending_tasks": [
                t
                for t in state.get("pending_tasks", [])
                if not (t.get("assigned_to") == self.name and t.get("status") == "open")
            ],
        }


problem_solver_node = ProblemSolverAgent()
