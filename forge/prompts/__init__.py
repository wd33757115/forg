"""Agent prompt templates."""

from forge.prompts.compliance import COMPLIANCE_SYSTEM
from forge.prompts.document import DOCUMENT_SYSTEM
from forge.prompts.problem_solver import PROBLEM_SOLVER_SYSTEM
from forge.prompts.problem_solver_prompt import (
    PROBLEM_SOLVER_REACT_TASK,
    PROBLEM_SOLVER_STRUCTURED_PROMPT,
)

__all__ = [
    "COMPLIANCE_SYSTEM",
    "DOCUMENT_SYSTEM",
    "PROBLEM_SOLVER_REACT_TASK",
    "PROBLEM_SOLVER_STRUCTURED_PROMPT",
    "PROBLEM_SOLVER_SYSTEM",
]
