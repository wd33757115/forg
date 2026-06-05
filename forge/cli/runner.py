"""Forge workflow runner for CLI and Web."""

from __future__ import annotations

from uuid import uuid4

from langchain_core.messages import HumanMessage

from forge.cli.demo_seed import apply_demo_evidence_seed
from forge.core import compile_workflow, create_initial_state
from forge.core.state import ProjectState
from forge.utils.env import load_dotenv
from forge.utils.logger import get_logger
from forge.utils.state_persistence import prepare_state_for_run


def run_forge(
    question: str,
    *,
    project_id: str = "cli-demo",
    protection_level: str = "3",
    problem_type_hint: str | None = None,
    check_mode: str | None = None,
    demo_seed: bool = False,
    initial_state: ProjectState | None = None,
) -> dict:
    """Execute the full Forge workflow from a fresh or resumed ProjectState."""
    load_dotenv()
    logger = get_logger("main")

    if initial_state is None:
        state = create_initial_state(project_id, current_phase="implementation")
        state["run_id"] = str(uuid4())[:8]
        state["messages"] = [HumanMessage(content=question)]
        state["rule_pack"] = {
            "pack_id": "system_integration_v1",
            "protection_level": protection_level,
        }
        if problem_type_hint:
            state["problem_type_hint"] = problem_type_hint
        if check_mode:
            state["check_mode"] = check_mode
        if demo_seed:
            state = apply_demo_evidence_seed(state)
    else:
        state = prepare_state_for_run(
            initial_state,
            question,
            protection_level=protection_level,
        )
        if problem_type_hint:
            state["problem_type_hint"] = problem_type_hint
        if check_mode:
            state["check_mode"] = check_mode

    logger.info(
        "Starting workflow | run_id=%s project=%s",
        state.get("run_id"),
        state.get("project_id"),
    )

    app = compile_workflow()
    return app.invoke(state)
