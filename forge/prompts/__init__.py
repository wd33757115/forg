"""Agent prompt templates."""

from forge.prompts.compliance import COMPLIANCE_SYSTEM
from forge.prompts.compliance_prompt import COMPLIANCE_REACT_TASK, COMPLIANCE_STRUCTURED_PROMPT
from forge.prompts.document import DOCUMENT_SYSTEM
from forge.prompts.problem_solver import PROBLEM_SOLVER_SYSTEM
from forge.prompts.operations_prompt import (
    OPERATIONS_REACT_TASK,
    OPERATIONS_STRUCTURED_PROMPT,
    OPERATIONS_SYSTEM,
)
from forge.prompts.pm_advisor_prompt import (
    PM_ADVISOR_REACT_TASK,
    PM_ADVISOR_STRUCTURED_PROMPT,
    PM_ADVISOR_SYSTEM,
)
from forge.prompts.security_prompt import (
    SECURITY_REACT_TASK,
    SECURITY_STRUCTURED_PROMPT,
    SECURITY_SYSTEM,
)
from forge.prompts.problem_solver_prompt import (
    PROBLEM_SOLVER_REACT_TASK,
    PROBLEM_SOLVER_STRUCTURED_PROMPT,
)

__all__ = [
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
