"""Basic Forge workflow demo — exercises Supervisor routing and agent stubs."""

from __future__ import annotations

from langchain_core.messages import HumanMessage

from forge.core import compile_workflow, create_initial_state, get_rule_pack
from forge.utils.env import load_dotenv
from forge.utils.llm import get_deepseek_api_key
from forge.utils.logging import get_logger

load_dotenv()
logger = get_logger("forge.example")


def main() -> None:
    if get_deepseek_api_key():
        logger.info("DeepSeek API key detected — agents will use LLM")
    else:
        logger.info("No API key — running in heuristic mode (set DEEPSEEK_API_KEY in .env)")

    # --- 1. Load Rule Packs ---
    packs = get_rule_pack()
    logger.info("Loaded Rule Packs: %s", list(packs.keys()))
    for mid, pack in packs.items():
        logger.info("  [%s] %s — %d rules", mid, pack.name, len(pack.rules))

    # --- 2. Initialize project state ---
    state = create_initial_state(
        project_id="demo-si-001",
        current_phase="implementation",
    )
    state["wbs"] = {
        "requirements": {"name": "需求分析", "status": "done"},
        "design": {"name": "方案设计", "status": "in_progress"},
    }

    # --- 3. Compile and run workflow (compliance scenario) ---
    app = compile_workflow()

    state["messages"] = [HumanMessage(content="请对项目进行等保合规检查")]
    state["pending_tasks"] = [
        {
            "id": "task-001",
            "title": "等保2.0合规扫描",
            "assigned_to": "compliance",
            "priority": "high",
            "status": "open",
        }
    ]

    logger.info("--- Running compliance scenario ---")
    result = app.invoke(state)
    _print_messages(result)

    # --- 4. Problem solver scenario ---
    state2 = create_initial_state(project_id="demo-si-002", current_phase="operations")
    state2["messages"] = [HumanMessage(content="用户登录接口返回401，请帮忙诊断")]
    state2["pending_tasks"] = [
        {
            "id": "task-002",
            "title": "登录认证故障诊断",
            "assigned_to": "problem_solver",
            "priority": "critical",
            "status": "open",
        }
    ]

    logger.info("--- Running problem solver scenario ---")
    result2 = app.invoke(state2)
    _print_messages(result2)

    # --- 5. Document generation scenario ---
    state3 = create_initial_state(project_id="demo-si-003")
    state3["messages"] = [HumanMessage(content="请生成等保合规材料大纲")]

    logger.info("--- Running document scenario ---")
    result3 = app.invoke(state3)
    _print_messages(result3)

    logger.info("Forge basic demo complete.")


def _print_messages(state: dict) -> None:
    for msg in state.get("messages", []):
        name = getattr(msg, "name", "user")
        content = getattr(msg, "content", str(msg))
        print(f"\n[{name}]\n{content[:500]}{'...' if len(content) > 500 else ''}")


if __name__ == "__main__":
    main()
