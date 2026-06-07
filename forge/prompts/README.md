# Forge Prompts 目录结构

每个 Agent 一个子目录，正文在 `prompts.py`：

```
prompts/
  problem_solver/prompts.py
  compliance/prompts.py
  security/prompts.py
  operations/prompts.py
  document/prompts.py
  pm_advisor/prompts.py
```

根目录 `*_prompt.py` 仅为**向后兼容重导出**。Agent 与业务代码请经中央 loader 引用（解耦）：

```python
from forge.prompts.loader import load_prompts

_ps = load_prompts("problem_solver")
PROBLEM_SOLVER_SYSTEM = _ps.PROBLEM_SOLVER_SYSTEM
```

新增 Agent 时在 `loader.py` 的 `_AGENT_PROMPT_MODULES` 注册模块名。

迁移脚本（可选）：`scripts/migrate_prompts.py`
