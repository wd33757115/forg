"""Agent prompt templates — prefer ``forge.prompts.loader`` for agent code."""

from forge.prompts.loader import get_prompt, list_registered_agents, load_prompts
from forge.prompts.compliance import COMPLIANCE_REACT_TASK, COMPLIANCE_STRUCTURED_PROMPT, COMPLIANCE_SYSTEM
from forge.prompts.document import DOCUMENT_SYSTEM
from forge.prompts.operations import OPERATIONS_REACT_TASK, OPERATIONS_STRUCTURED_PROMPT, OPERATIONS_SYSTEM
from forge.prompts.pm_advisor import PM_ADVISOR_REACT_TASK, PM_ADVISOR_STRUCTURED_PROMPT, PM_ADVISOR_SYSTEM
from forge.prompts.problem_solver import (
    PROBLEM_SOLVER_REACT_TASK,
    PROBLEM_SOLVER_STRUCTURED_PROMPT,
    PROBLEM_SOLVER_SYSTEM,
)
from forge.prompts.security import SECURITY_REACT_TASK, SECURITY_STRUCTURED_PROMPT, SECURITY_SYSTEM

__all__ = [
    "get_prompt",
    "load_prompts",
    "list_registered_agents",
    "COMPLIANCE_REACT_TASK",
    "COMPLIANCE_STRUCTURED_PROMPT",
    "COMPLIANCE_SYSTEM",
    "DOCUMENT_SYSTEM",
    "OPERATIONS_REACT_TASK",
    "OPERATIONS_STRUCTURED_PROMPT",
    "OPERATIONS_SYSTEM",
    "PM_ADVISOR_REACT_TASK",
    "PM_ADVISOR_STRUCTURED_PROMPT",
    "PM_ADVISOR_SYSTEM",
    "SECURITY_REACT_TASK",
    "SECURITY_STRUCTURED_PROMPT",
    "SECURITY_SYSTEM",
    "PROBLEM_SOLVER_REACT_TASK",
    "PROBLEM_SOLVER_STRUCTURED_PROMPT",
    "PROBLEM_SOLVER_SYSTEM",
]
