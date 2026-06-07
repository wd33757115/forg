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
from forge.agents.solution_output import RiskItem, RulePackReference, SolutionOption, SolutionOutput
from forge.core.state import WORKFLOW_PROBLEM_COMPLIANCE_LOOP, ProjectState
from forge.prompts.loader import load_prompts

_ps_prompts = load_prompts("problem_solver")
PROBLEM_SOLVER_SYSTEM = _ps_prompts.PROBLEM_SOLVER_SYSTEM
PROBLEM_SOLVER_REACT_TASK = _ps_prompts.PROBLEM_SOLVER_REACT_TASK
PROBLEM_SOLVER_STRUCTURED_PROMPT = _ps_prompts.PROBLEM_SOLVER_STRUCTURED_PROMPT
from forge.tools.problem_solver_tools import run_tool_research
from forge.core.confidence.config import PS_CONFIDENCE_DEFAULT_UNSET, PS_HEURISTIC_CONFIDENCE_CAP
from forge.utils.agent_context import build_handoff
from forge.utils.compliance_feedback import format_compliance_feedback_for_prompt
from forge.utils.conversation import record_conversation, record_thinking
from forge.utils.knowledge import append_knowledge, append_knowledge_to_state
from forge.utils.knowledge_memory import format_memory_context, search_similar_cases

def _format_execution_feedback(execution_results: list[dict[str, Any]] | None) -> str:
    """Format recent execution results into a prompt-friendly block for PS to learn from (D3 closed loop)."""
    if not execution_results:
        return "（无过往执行结果 — 首次或无执行反馈）"
    lines = ["## 过往执行反馈（execution_results — 请从中学习调整方案）"]
    for res in execution_results[-3:]:  # last few to keep context short
        tid = res.get("task_id", "?")
        status = res.get("status", "unknown")
        summary = (res.get("summary") or "")[:120]
        lines.append(f"- task={tid} status={status}: {summary}")
    lines.append("必须在 reasoning 中说明如何根据以上执行结果调整了推荐方案或 next_actions。")
    return "\n".join(lines)
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
    ) -> tuple[ProblemType, str, dict[str, str] | None, float]:
        """D4: returns (ptype, reason, conflict, classification_confidence)."""
        hint = state.get("problem_type") or state.get("problem_type_hint")
        ptype, reason, conflict, conf = classify_with_cli_hint(problem_statement, hint=hint)
        if conflict:
            self.logger.warning(
                "Problem type hint mismatch | %s",
                conflict.get("warning", conflict),
            )
        return ptype, reason, conflict, conf

    def _run_react(
        self,
        state: ProjectState,
        problem_statement: str,
        problem_type: ProblemType,
        type_reason: str,
        *,
        classification_conf: float = 0.7,
    ) -> str:
        """Run ReAct via BaseAgent helper + ToolRegistry tools (self.get_tools).

        D4: accepts classification_conf to adapt investigation strategy:
        - Low conf or mixed → use all modules + broader historical search + explicit self-critique instruction.
        """
        _ = self.get_tools(state)  # resolve via ToolRegistry; run_react uses same path
        is_uncertain = classification_conf < 0.55 or problem_type == "mixed"
        if is_uncertain:
            priority_modules = ", ".join(modules_for_problem_type("mixed"))  # all modules
        else:
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
        compliance_block = format_compliance_feedback_for_prompt(
            state.get("compliance_feedback")
        )
        exec_block = _format_execution_feedback(state.get("execution_results"))
        first_id = prior[0].get("id", "—") if prior else "—"
        self.logger.info(
            "ReAct prior_cases | count=%d first_id=%s problem_type=%s conf=%.2f uncertain=%s retry_feedback=%s exec_feedback=%s",
            len(prior),
            first_id,
            problem_type,
            classification_conf,
            is_uncertain,
            bool(state.get("compliance_feedback")),
            bool(state.get("execution_results")),
        )

        # D1: explicit project state snapshot for deeper reasoning (WBS/phase awareness)
        wbs = state.get("wbs", {})
        phase = state.get("current_phase", "")
        project_snapshot = f"阶段={phase}；WBS项={len(wbs)}；关键状态摘要={str(wbs)[:300]}"

        adaptation_note = ""
        if is_uncertain:
            adaptation_note = (
                "\n\n【D4 分类自适应】当前分类置信度较低或为 mixed，"
                "请：(1) 广泛查询所有 Rule Pack 模块；(2) 主动调用 search_historical_cases；"
                "(3) 在最终 Observation 后进行 self-critique：逐条核对 root_causes 是否被推荐方案直接缓解，"
                "以及 rule_pack_references 中的 rule_id 是否在 decision_rationale / compliance_impact 中被覆盖。"
            )

        task = PROBLEM_SOLVER_REACT_TASK.format(
            problem_statement=problem_statement,
            problem_type=problem_type,
            type_reason=type_reason,
            priority_modules=priority_modules,
            project_id=state.get("project_id", ""),
            current_phase=phase,
            enabled_modules=", ".join(state.get("enabled_modules", [])),
            prior_cases=prior_cases,
            compliance_feedback=compliance_block,
            execution_feedback=exec_block,
        ) + adaptation_note
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
        *,
        classification_conf: float = 0.7,
    ) -> SolutionOutput:
        """Produce validated SolutionOutput via LLM structured output or heuristic builder.

        D4: uses classification_conf to inject adaptation/self-critique guidance into the prompt
        and to bias _validate_solution_output (wider rule queries already done in ReAct).
        """
        compliance_block = format_compliance_feedback_for_prompt(
            state.get("compliance_feedback")
        )
        exec_block = _format_execution_feedback(state.get("execution_results"))

        is_uncertain = classification_conf < 0.55 or problem_type == "mixed"
        adaptation_block = ""
        if is_uncertain:
            adaptation_block = (
                "\n\n【D4 分类自适应 — 低置信度/mixed】请在 reasoning 中加入 self-critique 段落："
                "1) 列出 top-2 root_causes；2) 说明推荐方案如何直接缓解它们；3) 逐条确认 rule_pack_references 的 rule_id "
                "是否出现在 decision_rationale、compliance_impact 或 next_actions 中。若缺口则在 next_actions 补充具体动作。"
            )

        # D1: pass project snapshot into structured synthesis for state-aware reasoning
        wbs = state.get("wbs", {})
        phase = state.get("current_phase", "")
        project_snapshot = f"阶段={phase}；WBS项={len(wbs)}；关键状态摘要={str(wbs)[:300]}"

        prompt = PROBLEM_SOLVER_STRUCTURED_PROMPT.format(
            problem_statement=problem_statement,
            problem_type=problem_type,
            type_reason=type_reason,
            research_context=escape_braces_for_format(research_context[:12000]),
            compliance_feedback=compliance_block,
            execution_feedback=exec_block,
        ) + adaptation_block
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
            result.solution_source = "llm"
            return self._validate_solution_output(
                result,
                problem_statement=problem_statement,
                problem_type=problem_type,
                research_context=research_context,
                solution_source="llm",
                compliance_feedback=state.get("compliance_feedback"),
                classification_conf=classification_conf,
                state=state,
            )

        heuristic = self._build_heuristic_solution(
            state, problem_statement, research_context, problem_type, type_reason
        )
        heuristic.solution_source = "heuristic"
        return self._validate_solution_output(
            heuristic,
            problem_statement=problem_statement,
            problem_type=problem_type,
            research_context=research_context,
            solution_source="heuristic",
            compliance_feedback=state.get("compliance_feedback"),
            classification_conf=classification_conf,
            state=state,
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
        check_mode = state.get("check_mode")
        rule_refs = fetch_relevant_rules(problem_type, problem_statement, minimum=3, check_mode=check_mode)
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
        check_mode: str | None = None,
    ) -> None:
        """Merge research-extracted rule_ids and keyword-based defaults (in-place).

        D2: forwards check_mode so strict mode prefers high-severity clauses.
        """
        extracted = extract_rule_ids_from_text(research_context)
        base = fetch_relevant_rules(problem_type, problem_statement, minimum=3, check_mode=check_mode)
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
        solution_source: str = "llm",
        compliance_feedback: dict[str, Any] | None = None,
        state: ProjectState | dict | None = None,
        classification_conf: float | None = None,
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
            check_mode = (state or {}).get("check_mode") if state else None
            self._enrich_rule_pack_references(
                output,
                problem_statement=problem_statement or output.problem_analysis,
                problem_type=ptype,
                research_context=research_context,
                check_mode=check_mode,
            )
        self._ensure_decision_rationale(output)
        output.solution_source = solution_source  # type: ignore[assignment]
        self._ensure_reasoning_confidence(
            output,
            research_context=research_context,
            solution_source=solution_source,
            state=state,
        )
        self._ensure_reasoning_has_rule_ids(output)
        self._ensure_rule_causal_explanation(output)  # D2: force explicit rule_id causal sentences
        self._ensure_prior_case_reasoning(output, research_context=research_context)
        exec_block = _format_execution_feedback(state.get("execution_results") if state else None)
        self._ensure_execution_learning(output, exec_block)  # D3 closed loop
        self._ensure_self_critique(output, classification_conf=classification_conf)  # D4 light self-critique for uncertain cases
        self._ensure_risk_summary(output)
        self._apply_compliance_feedback_to_output(output, compliance_feedback)

        # D1: enrich depth fields (assumptions, risks, alternatives, snapshot, structured reasoning)
        # state may be None in some legacy call paths; enrich is defensive
        self._enrich_solution_depth(output, state=state or {}, research_context=research_context)
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
    def _ensure_rule_causal_explanation(output: SolutionOutput) -> None:
        """D2: ensure reasoning contains explicit causal links for the top rule refs.

        If the LLM output is weak on "why this rule matters for this phenomenon",
        we append a compact causal sentence using the ref.relevance (which is required
        to be phenomenon→rule).
        """
        if not output.reasoning:
            return
        refs = output.rule_pack_references or []
        if not refs:
            return

        # Already has decent causal language?
        causal_markers = ("因为", "导致", "对应", "满足", "对齐", "约束", "要求", "核查")
        low = output.reasoning.lower()
        if any(m in low for m in causal_markers) and _RULE_ID_IN_TEXT.search(output.reasoning):
            return

        # Build a compact causal tail from the best refs (prefer high causal_quality if present)
        sorted_refs = sorted(
            refs[:4],
            key=lambda r: getattr(r, "causal_quality", 0.0),
            reverse=True,
        )
        clauses = []
        for r in sorted_refs[:2]:
            rel = (r.relevance or "").strip()
            if rel and (r.rule_id in output.reasoning or r.rule_id.lower() in low):
                # already mentioned, skip to avoid duplication
                continue
            if rel:
                clauses.append(f"{rel}（{r.rule_id}）")
        if clauses:
            tail = "；".join(clauses)
            output.reasoning = f"{output.reasoning.rstrip()}；{tail}"

    @staticmethod
    def _ensure_execution_learning(output: SolutionOutput, execution_feedback: str) -> None:
        """D3: force the solution to explicitly reference and learn from past execution results.

        If execution feedback block indicates previous runs, ensure reasoning mentions
        at least one concrete outcome and an adjustment made this time.
        """
        if not execution_feedback or "无过往执行结果" in execution_feedback:
            return
        if "执行" in (output.reasoning or "") or "execution" in (output.reasoning or "").lower():
            return  # already addressed
        # Extract a hint from the block
        hint = ""
        for line in execution_feedback.splitlines():
            if "status=" in line and "task=" in line:
                hint = line.strip()[:100]
                break
        if hint:
            output.reasoning = (
                f"{output.reasoning.rstrip()}；"
                f"参考过往执行 {hint}，本次调整了方案/下一步行动以避免重复问题。"
            )
        else:
            output.reasoning = (
                f"{output.reasoning.rstrip()}；"
                "已参考过往执行结果调整本次推荐。"
            )

    @staticmethod
    def _ensure_self_critique(
        output: SolutionOutput,
        *,
        classification_conf: float | None = None,
    ) -> None:
        """D4 light self-critique: for uncertain/low-conf classifications, force explicit linkage check.

        If the output lacks clear mapping from root_causes → recommended solution and cited rule_ids,
        we append a critique sentence to reasoning and ensure at least one remediation next_action.
        This is the "prompt里的 self-check 步骤" realized as reliable post-processing.
        """
        if not output.reasoning:
            return
        conf = classification_conf if classification_conf is not None else 0.7
        if conf >= 0.65 and output.problem_type != "mixed":
            # High confidence single-domain: light touch only
            if output.rule_pack_references and not any(r.rule_id in (output.decision_rationale or "") for r in output.rule_pack_references[:1]):
                output.reasoning = f"{output.reasoning.rstrip()}；自检：推荐理由已引用规则。"
            return

        # Uncertain / mixed / low conf: stricter self-critique
        root_keywords = [c.lower() for c in (output.root_causes or [])]
        rec = next((s for s in output.solutions if s.id == output.recommended_solution_id), None)
        rec_text = " ".join([
            (rec.description if rec else ""),
            (rec.approach if rec else ""),
            output.decision_rationale or "",
        ]).lower()

        covered_roots = sum(1 for kw in root_keywords if kw and kw[:8] in rec_text) if root_keywords else 1
        cited_rules = [r.rule_id for r in (output.rule_pack_references or [])]
        rules_in_rationale = sum(1 for rid in cited_rules if rid and rid in (output.decision_rationale or "") + " " + (rec.compliance_impact if rec else ""))

        gaps: list[str] = []
        if covered_roots < max(1, len(root_keywords) // 2):
            gaps.append("根因覆盖不足")
        if cited_rules and rules_in_rationale < min(2, len(cited_rules)):
            gaps.append("规则引用未在推荐理由中充分体现")

        if gaps:
            critique = "；自检发现缺口（" + "、".join(gaps) + "），已补充 next_actions 强化对齐。"
            if "自检" not in output.reasoning:
                output.reasoning = f"{output.reasoning.rstrip()}{critique}"
            for rid in cited_rules[:2]:
                act = f"自检对齐 `{rid}`：确认方案与根因/规则的一致性"
                if act not in output.next_actions:
                    output.next_actions.append(act)

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
        prior_cases: list[dict[str, Any]] | None = None,
        execution_results: list[dict[str, Any]] | None = None,
    ) -> float:
        """A4 + D3: confidence from ref coverage, relevance, tool evidence, history match, and past execution outcomes."""
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

        # D3: history & execution factors
        history_bonus = 0.0
        if prior_cases:
            positive = sum(1 for p in prior_cases if p.get("outcome") in ("success", "compliant", "resolved", "positive"))
            if positive:
                history_bonus = min(0.12, positive * 0.04)
        exec_factor = 0.0
        if execution_results:
            successes = sum(1 for e in execution_results if e.get("status") in ("success", "completed", "ok"))
            fails = sum(1 for e in execution_results if e.get("status") in ("failed", "error", "blocked"))
            if successes:
                exec_factor += min(0.08, successes * 0.03)
            if fails:
                exec_factor -= min(0.10, fails * 0.04)

        raw = (
            0.30 * ref_score
            + 0.20 * tool_score
            + 0.15 * sol_score
            + 0.15 * rationale_score
            + 0.10 * reasoning_score
            + 0.10 * (high_q / max(1, ref_n))
            + history_bonus
            + exec_factor
        )
        return round(min(1.0, max(0.0, raw - pad_penalty)), 2)

    @staticmethod
    def _finalize_confidence(
        output: SolutionOutput,
        *,
        research_context: str = "",
        solution_source: str = "llm",
        prior_cases: list[dict[str, Any]] | None = None,
        execution_results: list[dict[str, Any]] | None = None,
    ) -> None:
        """Cap confidence: min(LLM self-score, computed); heuristic path has hard cap.
        D3: passes history and execution context into the core computation.
        """
        computed = ProblemSolverAgent._compute_confidence(
            output,
            research_context=research_context,
            prior_cases=prior_cases,
            execution_results=execution_results,
        )
        llm_conf = output.confidence
        if llm_conf == PS_CONFIDENCE_DEFAULT_UNSET:
            final = computed
        else:
            final = min(llm_conf, computed)
        if solution_source == "heuristic":
            final = min(final, PS_HEURISTIC_CONFIDENCE_CAP)
        output.confidence = final

    @staticmethod
    def _ensure_reasoning_confidence(
        output: SolutionOutput,
        *,
        research_context: str = "",
        solution_source: str = "llm",
        state: ProjectState | dict | None = None,
    ) -> None:
        """Fill reasoning and confidence when structured output omitted them.
        D3: accepts state so confidence can factor execution history.
        """
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

        exec_for_conf = (state or {}).get("execution_results") if state else None
        ProblemSolverAgent._finalize_confidence(
            output,
            research_context=research_context,
            solution_source=solution_source,
            execution_results=exec_for_conf,
        )

        if output.confidence >= 0.75 and refs:
            output.reasoning = (
                f"{output.reasoning.rstrip()}；"
                f"置信度={output.confidence}（引用覆盖+工具证据，已取 min(LLM, 计算值)）"
            )

    @staticmethod
    def _ensure_risk_summary(output: SolutionOutput) -> None:
        if output.risk_summary:
            return
        rec = next(
            (s for s in output.solutions if s.id == output.recommended_solution_id),
            output.solutions[0] if output.solutions else None,
        )
        level = rec.risk_level if rec else "medium"
        output.risk_summary = (
            f"推荐方案残余风险等级为 {level}；"
            "需持续监控合规证据与变更回滚路径。"
        )

    @staticmethod
    def _apply_compliance_feedback_to_output(
        output: SolutionOutput,
        feedback: dict[str, Any] | None,
    ) -> None:
        """Ensure retry solutions cite failed rule_ids and add remediation next_actions."""
        if not feedback:
            return
        failed_ids = feedback.get("failed_rule_ids") or [
            f.get("rule_id") for f in (feedback.get("failed_items") or []) if f.get("rule_id")
        ]
        if not failed_ids:
            return
        if "合规重试" not in (output.reasoning or ""):
            output.reasoning = (
                f"{output.reasoning.rstrip()}；"
                f"合规重试 #{feedback.get('retry_count', '?')} 须覆盖: "
                f"{', '.join(failed_ids[:6])}"
            )
        for item in (feedback.get("failed_items") or [])[:4]:
            rid = item.get("rule_id")
            if not rid:
                continue
            action = f"整改 `{rid}` ({item.get('severity', '—')}): {(item.get('suggestion') or '')[:80]}"
            if action not in output.next_actions:
                output.next_actions.append(action)

    def _enrich_solution_depth(
        self,
        output: SolutionOutput,
        *,
        state: ProjectState | dict | None = None,
        research_context: str = "",
    ) -> None:
        """D1: populate assumptions, risks, alternatives, snapshot and structure reasoning if shallow (Category 1/5)."""
        # Project snapshot (state awareness)
        if not output.project_state_snapshot:
            st = state or {}
            wbs = st.get("wbs", {}) if isinstance(st, dict) else getattr(st, "wbs", {})
            phase = st.get("current_phase", "") if isinstance(st, dict) else getattr(st, "current_phase", "")
            output.project_state_snapshot = f"阶段={phase}；WBS项={len(wbs) if isinstance(wbs, (dict, list)) else 0}"

        # Assumptions
        if not output.assumptions:
            output.assumptions = [
                "项目当前阶段与资源允许按推荐方案推进",
                "关键干系人可协调",
            ]

        # Risks (structured)
        if not output.risks:
            rec = next(
                (s for s in output.solutions if s.id == output.recommended_solution_id),
                output.solutions[0] if output.solutions else None,
            )
            sev = rec.risk_level if rec else "medium"
            output.risks = [
                RiskItem(
                    title="推荐方案执行后残余风险",
                    severity=sev,
                    likelihood="medium",
                    mitigation="加强监控与回滚准备",
                    related_rule_ids=[r.rule_id for r in output.rule_pack_references[:2]],
                )
            ]

        # D3: pull explicit risk lessons from prior failed cases or past execution failures in state
        if state:
            st = state if isinstance(state, dict) else getattr(state, "__dict__", {})
            prior = st.get("knowledge_base") or []
            execs = st.get("execution_results") or []
            for p in prior:
                if p.get("outcome") in ("failure", "non_compliant", "error") and p.get("content"):
                    output.risks.append(
                        RiskItem(
                            title=f"历史同类问题复发风险（参考 {p.get('id','case')}）",
                            severity="medium",
                            likelihood="medium",
                            mitigation=(p.get("content") or "")[:80],
                            related_rule_ids=p.get("related_rules") or [],
                        )
                    )
                    break
            for e in execs[-2:]:
                if e.get("status") in ("failed", "error"):
                    output.risks.append(
                        RiskItem(
                            title=f"上一次执行失败复发（{e.get('task_id','task')}）",
                            severity="high",
                            likelihood="medium",
                            mitigation=(e.get("summary") or "检查执行条件与依赖")[:80],
                            related_rule_ids=[],
                        )
                    )
                    break

        # Alternatives
        if not output.alternatives and len(output.solutions) >= 2:
            others = [s.id for s in output.solutions if s.id != output.recommended_solution_id]
            output.alternatives = (
                f"考虑过 {', '.join(others)}；因紧急性/合规覆盖/成本选择当前推荐。"
            )

        # Light structure on reasoning if flat
        if output.reasoning and len(output.reasoning) > 40:
            if "1)" not in output.reasoning and "项目状态" not in output.reasoning:
                snap = output.project_state_snapshot or ""
                output.reasoning = f"项目状态：{snap}。\n" + output.reasoning

        if output.risks and not output.risk_summary:
            output.risk_summary = "; ".join(r.title for r in output.risks[:2])

    @staticmethod
    def _ensure_prior_case_reasoning(
        output: SolutionOutput,
        *,
        research_context: str = "",
    ) -> None:
        """D3 strengthened: when research mentions prior cases, reasoning must cite specific outcome and lesson."""
        if "历史案例" not in research_context and "outcome=" not in research_context:
            return
        if not output.reasoning:
            return
        if "历史案例" in output.reasoning and ("outcome=" in output.reasoning or "参考了" in output.reasoning):
            return  # already specific
        # Try to pull a concrete hint
        hint = ""
        for line in research_context.splitlines():
            if "outcome=" in line and "[" in line:
                hint = line.strip()[:90]
                break
        if hint:
            output.reasoning = (
                f"{output.reasoning.rstrip()}；"
                f"参考历史案例 {hint}，因此本次优先采用其成功做法。"
            )
        else:
            output.reasoning = (
                f"{output.reasoning.rstrip()}；"
                "已对照 knowledge_base 历史案例（含 outcome）调整方案优先级。"
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

        problem_type, type_reason, classification_conflict, classification_conf = self._classify(
            state, problem_statement
        )
        self.logger.info(
            "Problem classified | type=%s reason=%s conf=%.2f uncertain=%s",
            problem_type,
            type_reason,
            classification_conf,
            classification_conf < 0.55 or problem_type == "mixed",
        )

        research_context = self._run_react(
            state, problem_statement, problem_type, type_reason, classification_conf=classification_conf
        )
        solution = self._synthesize_structured(
            state, problem_statement, research_context, problem_type, type_reason,
            classification_conf=classification_conf,
        )

        retry_count = state.get("compliance_retry_count", 0)
        feedback = state.get("compliance_feedback")
        if retry_count > 0 and feedback:
            failed_ids = feedback.get("failed_rule_ids") or []
            solution.problem_analysis += (
                f"\n\n[合规重试 #{retry_count}] 状态={feedback.get('compliance_status')}；"
                f"须处置 failed rule_id: {', '.join(failed_ids[:6]) or '见 compliance_feedback'}"
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
