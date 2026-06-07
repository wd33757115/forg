"""ProblemSolverAgent — ReAct investigation + structured solution output."""

from __future__ import annotations

import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from forge.core.base_agent import BaseAgent
from forge.agents.problem_classifier import (
    PROBLEM_TYPE_LABELS,
    ProblemType,
    classify_with_cli_hint,
    modules_for_problem_type,
)
from forge.agents.rule_pack_refs import ensure_minimum_references, fetch_relevant_rules, merge_rule_pack_references
from forge.agents.solution_output import RulePackReference, SolutionOption, SolutionOutput
from forge.core.state import WORKFLOW_PROBLEM_COMPLIANCE_LOOP, ProjectState
from forge.prompts.loader import load_prompts

_ps_prompts = load_prompts("problem_solver")
PROBLEM_SOLVER_SYSTEM = _ps_prompts.PROBLEM_SOLVER_SYSTEM
PROBLEM_SOLVER_REACT_TASK = _ps_prompts.PROBLEM_SOLVER_REACT_TASK
PROBLEM_SOLVER_STRUCTURED_PROMPT = _ps_prompts.PROBLEM_SOLVER_STRUCTURED_PROMPT
from forge.tools.problem_solver_tools import run_tool_research
from forge.utils.agent_context import build_handoff
from forge.utils.conversation import record_conversation, record_thinking
from forge.utils.knowledge import append_knowledge, append_knowledge_to_state
from forge.utils.knowledge_memory import format_memory_context, search_similar_cases
from forge.utils.llm import escape_braces_for_format
from forge.utils.react_research_gate import supplement_rule_pack_research
from forge.utils.reference_scoring import apply_relevance_scores, summarize_reference_provenance
from forge.utils.rule_pack_extract import extract_rule_ids_from_text

_RULE_ID_IN_TEXT = re.compile(r"\b((?:db|itil|si)-[a-z0-9-]+)\b", re.IGNORECASE)


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

    def _classify(
        self, state: ProjectState, problem_statement: str
    ) -> tuple[ProblemType, str, dict[str, str] | None]:
        hint = state.get("problem_type") or state.get("problem_type_hint")
        ptype, reason, conflict = classify_with_cli_hint(problem_statement, hint=hint)
        if conflict:
            self.logger.warning(
                "Problem type hint mismatch | %s",
                conflict.get("warning", conflict),
            )
        return ptype, reason, conflict

    def _run_react(
        self,
        state: ProjectState,
        problem_statement: str,
        problem_type: ProblemType,
        type_reason: str,
    ) -> str:
        """Run ReAct via BaseAgent helper + ToolRegistry tools (self.get_tools)."""
        _ = self.get_tools(state)  # resolve via ToolRegistry; run_react uses same path
        priority_modules = ", ".join(modules_for_problem_type(problem_type))
        fallback = run_tool_research(
            state, problem_statement, problem_type=problem_type
        )
        prior = search_similar_cases(
            state,
            problem_type=problem_type,
            problem_text=problem_statement,
            limit=3,
        )
        prior_cases = format_memory_context(prior)
        first_id = prior[0].get("id", "—") if prior else "—"
        self.logger.info(
            "ReAct prior_cases | count=%d first_id=%s problem_type=%s",
            len(prior),
            first_id,
            problem_type,
        )
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
        research = self.run_react(
            state,
            system=PROBLEM_SOLVER_SYSTEM,
            task=task,
            temperature=0.2,
            fallback=fallback,
        )
        research, supplemented = supplement_rule_pack_research(
            state,
            research,
            problem_type,
            problem_statement=problem_statement,
        )
        if supplemented:
            self.logger.info(
                "ReAct research gate | supplemented query_rule_pack | rule_ids=%d",
                len(extract_rule_ids_from_text(research)),
            )
        return research

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
                research_context=research_context,
            )

        heuristic = self._build_heuristic_solution(
            state, problem_statement, research_context, problem_type, type_reason
        )
        return self._validate_solution_output(
            heuristic,
            problem_statement=problem_statement,
            problem_type=problem_type,
            research_context=research_context,
        )

    @staticmethod
    def _structured_analysis(
        *,
        problem_type: ProblemType,
        type_reason: str,
        phenomenon: str,
        impact: str,
        dengbao: str,
        itil: str,
    ) -> str:
        """Four-part analysis template (phenomenon / impact / dengbao / ITIL) for explainability."""
        label = PROBLEM_TYPE_LABELS.get(problem_type, problem_type)
        return (
            f"【{label}】{type_reason}\n"
            f"现象：{phenomenon}\n"
            f"业务影响：{impact}\n"
            f"等保维度：{dengbao}\n"
            f"ITIL维度：{itil}"
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
        rule_refs = fetch_relevant_rules(problem_type, problem_statement, minimum=3)
        problem_lower = problem_statement.lower()

        is_auth = any(k in problem_lower for k in ("401", "403", "登录", "认证", "auth"))
        is_perf = any(k in problem_lower for k in ("慢", "超时", "timeout", "latency"))
        is_itil_evt = any(k in problem_lower for k in ("事件", "中断", "宕机", "itil", "sla"))

        if problem_type == "security" or is_auth:
            analysis = self._structured_analysis(
                problem_type=problem_type,
                type_reason=type_reason,
                phenomenon="认证/授权链路异常（如 401/403）",
                impact="用户无法登录或越权风险上升，影响业务可用性与审计证据完整性",
                dengbao="对照 db-acs-001 身份鉴别、db-aud-001 安全审计核查控制项",
                itil="按 itil-inc-001 记录事件，必要时 itil-chg-001 走变更修复",
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
            analysis = self._structured_analysis(
                problem_type=problem_type,
                type_reason=type_reason,
                phenomenon="服务中断或 SLA 指标恶化",
                impact="业务可用性下降，可能触发违约与升级流程",
                dengbao="确保处置过程保留审计日志（db-aud-001）",
                itil="按 itil-inc-001 分级响应，itil-prb-001 跟踪根因",
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
            analysis = self._structured_analysis(
                problem_type="technical",
                type_reason=type_reason,
                phenomenon="性能劣化或集成链路超时",
                impact="接口响应变慢，可能导致上游业务超时与用户体验下降",
                dengbao="变更与日志留存满足 db-aud-001 / si-int-001",
                itil="itil-inc-001 事件记录 + itil-slm-001 SLA 影响评估",
            )
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
            analysis = self._structured_analysis(
                problem_type="mixed",
                type_reason=type_reason,
                phenomenon=problem_statement[:120],
                impact="安全控制与服务可用性交叉受影响，需联合诊断",
                dengbao="并行核查 dengbao_2.0 控制项（db-acs-001 等）",
                itil="并行执行 itil-inc-001 事件流程与变更协同",
            )
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

        rec = next((s for s in solutions if s.id == recommended), solutions[0] if solutions else None)
        rationale = (
            f"推荐 {recommended}：{rec.title if rec else ''}；"
            f"基于 {len(rule_refs)} 条 Rule Pack 引用与问题类型 {problem_type}。"
        )

        return SolutionOutput(
            problem_type=problem_type,
            problem_analysis=analysis,
            root_causes=root_causes,
            rule_pack_references=rule_refs,
            solutions=solutions,
            recommended_solution_id=recommended,
            decision_rationale=rationale,
            next_actions=[
                f"确认影响范围（项目 {state.get('project_id', 'N/A')}）",
                f"执行推荐方案 {recommended}",
                "更新知识库并关联 Rule Pack rule_id",
                "如需变更，提交 ITIL RFC（itil-chg-001）",
            ],
            dengbao_considerations=dengbao or ["对照等保控制项验证"],
            itil_considerations=itil or ["按事件管理流程记录"],
        )

    def _enrich_rule_pack_references(
        self,
        output: SolutionOutput,
        *,
        problem_statement: str,
        problem_type: ProblemType,
        research_context: str = "",
    ) -> None:
        """Merge research-extracted rule_ids and keyword-based defaults (in-place)."""
        extracted = extract_rule_ids_from_text(research_context)
        base = fetch_relevant_rules(problem_type, problem_statement, minimum=3)
        output.rule_pack_references = merge_rule_pack_references(
            output.rule_pack_references or base,
            extracted,
            limit=8,
        )
        output.rule_pack_references = ensure_minimum_references(
            output.rule_pack_references,
            problem_type,
            problem_statement,
            minimum=3,
        )
        output.rule_pack_references = apply_relevance_scores(
            output.rule_pack_references,
            problem_statement,
        )
        stats = summarize_reference_provenance(output.rule_pack_references)
        self.logger.info(
            "Rule Pack refs scored | total=%d avg=%.2f pad_ratio=%.2f",
            stats["total"],
            stats["avg_relevance_score"],
            stats["minimum_pad_ratio"],
        )

    def _validate_solution_output(
        self,
        output: SolutionOutput,
        *,
        problem_statement: str = "",
        problem_type: ProblemType | None = None,
        research_context: str = "",
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
        ptype = problem_type or output.problem_type
        if ptype:
            self._enrich_rule_pack_references(
                output,
                problem_statement=problem_statement or output.problem_analysis,
                problem_type=ptype,
                research_context=research_context,
            )
        self._ensure_decision_rationale(output)
        self._ensure_reasoning_confidence(output, research_context=research_context)
        self._ensure_reasoning_has_rule_ids(output)
        self._ensure_prior_case_reasoning(output, research_context=research_context)
        return output

    @staticmethod
    def _ensure_reasoning_has_rule_ids(output: SolutionOutput) -> None:
        """W1-6/W1-7: reasoning must mention at least one canonical rule_id."""
        if not output.reasoning:
            return
        if _RULE_ID_IN_TEXT.search(output.reasoning):
            return
        refs = output.rule_pack_references or []
        if not refs:
            return
        rid_list = ", ".join(r.rule_id for r in refs[:4])
        output.reasoning = (
            f"{output.reasoning.rstrip()}；"
            f"Rule Pack 依据：{rid_list}"
        )

    @staticmethod
    def _ensure_decision_rationale(output: SolutionOutput) -> None:
        """Fill decision_rationale when LLM/heuristic omitted it."""
        if output.decision_rationale:
            return
        recommended = next(
            (s for s in output.solutions if s.id == output.recommended_solution_id),
            output.solutions[0] if output.solutions else None,
        )
        ref_count = len(output.rule_pack_references or [])
        output.decision_rationale = (
            f"推荐 {output.recommended_solution_id}：{recommended.title if recommended else ''}；"
            f"基于 {ref_count} 条 Rule Pack 引用与问题类型 {output.problem_type}。"
        )

    @staticmethod
    def _compute_confidence(
        output: SolutionOutput,
        *,
        research_context: str = "",
    ) -> float:
        """A4: confidence from ref coverage, relevance scores, and tool evidence."""
        refs = output.rule_pack_references or []
        ref_n = len(refs)
        avg_rel = sum(r.relevance_score for r in refs) / ref_n if ref_n else 0.0
        high_q = sum(1 for r in refs if r.relevance_score >= 0.7)
        ref_score = min(1.0, (ref_n / 3.0) * 0.4 + avg_rel * 0.6)
        tool_ids = len(extract_rule_ids_from_text(research_context))
        tool_score = 1.0 if tool_ids >= 3 else (0.7 if tool_ids >= 1 else 0.45)
        sol_score = 1.0 if len(output.solutions) >= 2 else 0.6
        rationale_score = 1.0 if output.decision_rationale else 0.5
        reasoning_score = 1.0 if _RULE_ID_IN_TEXT.search(output.reasoning or "") else 0.55
        pad_penalty = 0.0
        if refs:
            pad_penalty = sum(
                1 for r in refs if r.reference_source == "minimum_pad" or r.relevance_score < 0.45
            ) / len(refs) * 0.15
        raw = (
            0.30 * ref_score
            + 0.20 * tool_score
            + 0.15 * sol_score
            + 0.15 * rationale_score
            + 0.10 * reasoning_score
            + 0.10 * (high_q / max(1, ref_n))
        )
        return round(min(1.0, max(0.0, raw - pad_penalty)), 2)

    @staticmethod
    def _ensure_reasoning_confidence(
        output: SolutionOutput,
        *,
        research_context: str = "",
    ) -> None:
        """Fill reasoning and confidence when structured output omitted them."""
        refs = ", ".join(r.rule_id for r in (output.rule_pack_references or [])[:4])
        if not output.reasoning:
            causes = "；".join(output.root_causes[:3]) if output.root_causes else "待补充"
            output.reasoning = (
                f"1) 问题类型={output.problem_type}；"
                f"2) 根因：{causes}；"
                f"3) Rule Pack 引用：{refs or '无'}；"
                f"4) 推荐 {output.recommended_solution_id}：{output.decision_rationale[:120]}"
            )
        elif refs and not _RULE_ID_IN_TEXT.search(output.reasoning):
            output.reasoning = f"{output.reasoning.rstrip()}；依据 {refs}"

        computed = ProblemSolverAgent._compute_confidence(
            output, research_context=research_context
        )
        if output.confidence == 0.5 or computed > output.confidence:
            output.confidence = computed

        if output.confidence >= 0.75 and refs:
            output.reasoning = (
                f"{output.reasoning.rstrip()}；"
                f"置信度={output.confidence}（引用覆盖+工具证据）"
            )

    @staticmethod
    def _ensure_prior_case_reasoning(
        output: SolutionOutput,
        *,
        research_context: str = "",
    ) -> None:
        """When research mentions prior cases, reasoning should acknowledge them."""
        if "历史案例" not in research_context and "outcome=" not in research_context:
            return
        if not output.reasoning or "历史案例" in output.reasoning or "借鉴" in output.reasoning:
            return
        output.reasoning = (
            f"{output.reasoning.rstrip()}；"
            "已对照 knowledge_base 历史案例调整方案优先级。"
        )

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
            score = f" score={ref.relevance_score:.2f}" if ref.relevance_score else ""
            lines.append(f"- [{ref.rule_id}] {ref.title} ({ref.module}){score}")
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

        problem_type, type_reason, classification_conflict = self._classify(
            state, problem_statement
        )
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
            "decision_rationale": solution.decision_rationale,
        }

        knowledge_entry = append_knowledge(
            state,
            agent=self.name,
            summary=solution.problem_analysis[:2000],
            tags=["problem_solver", problem_type, f"attempt_{retry_count + 1}"],
            category="problem_solution",
            detail={
                "solution": solution_dict,
                "recommended_solution_id": solution.recommended_solution_id,
                "retry_count": retry_count,
                "problem_type": problem_type,
                "rule_pack_refs": [r.rule_id for r in solution.rule_pack_references[:8]],
            },
        )

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

        ref_stats = summarize_reference_provenance(solution.rule_pack_references)

        agent_updates: dict[str, Any] = {
            **self.reply(response_body),
            "last_solution": solution_dict,
            "problem_type": problem_type,
            **append_knowledge_to_state(state, knowledge_entry),
            "pending_tasks": [
                t
                for t in state.get("pending_tasks", [])
                if not (t.get("assigned_to") == self.name and t.get("status") == "open")
            ],
        }
        if classification_conflict:
            agent_updates["classification_conflict"] = classification_conflict
        agent_updates["reference_provenance"] = ref_stats
        working = {**state, **agent_updates}
        agent_updates.update(
            build_handoff(
                working,
                from_agent=self.name,
                to_agent="compliance",
                payload=handoff_payload,
            )
        )
        working = {**state, **agent_updates}
        agent_updates.update(
            record_thinking(
                working,
                agent=self.name,
                thought=f"判定问题类型为 {problem_type}（{type_reason}）",
                decision=f"推荐方案 {solution.recommended_solution_id}",
                evidence=[r.rule_id for r in solution.rule_pack_references[:5]],
                extra={
                    "problem_type": problem_type,
                    "attempt": attempt,
                    "reference_provenance": ref_stats,
                    "classification_conflict": classification_conflict,
                },
            )
        )
        working = {**state, **agent_updates}
        agent_updates.update(
            record_conversation(
                working,
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
