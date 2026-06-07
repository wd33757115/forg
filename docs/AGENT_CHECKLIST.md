# 新增 Agent 接入 Checklist

> 阶段 2 完成标准：按本清单接入新 Agent，无需修改 Supervisor 主体逻辑。

## 1. Agent 实现

- [ ] `forge/agents/<name>.py` — 继承 `BaseAgent`，实现 `run(state) -> dict`
- [ ] `forge/agents/<name>_output.py` — Pydantic 输出，继承 `AgentOutputBase`

## 2. 工具与注册

- [ ] `forge/tools/<name>_tools.py` — `build_<name>_tools(state)`，**不** import agents
- [ ] `ToolRegistry.register("<name>", build_<name>_tools)` in `core/tool_registry.py`

## 3. AgentRegistry（工作流节点）

- [ ] 在 `core/agent_registry.py` `_register_builtin_agents` 注册 `wrap_agent_node(<node>, "<name>")`
- [ ] 在 `core/workflow.py` 添加节点与边
- [ ] 若需新路由：在 `core/supervisor_routing.py` 添加 `route_after_*`

## 4. Prompts

- [ ] `forge/prompts/<name>/prompts.py` — SYSTEM / REACT / STRUCTURED
- [ ] 在 `forge/prompts/loader.py` 注册模块；Agent 通过 `load_prompts("<name>")` 引用，**不**直引 `prompts.<name>.prompts`

## 5. Supervisor 路由（如需要）

- [ ] `AgentName` 枚举新增值
- [ ] `route_after_*` 条件边（尽量复用现有队列模式）

## 6. 测试

- [ ] `tests/test_<name>.py` — 离线可测
- [ ] 更新 `tests/test_agent_decoupling.py` 门禁（无直连 `build_*_tools`）

## 7. 文档

- [ ] README 功能表
- [ ] `docs/ARCHITECTURE.md` §A.10 如有契约变更
