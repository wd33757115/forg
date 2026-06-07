# Forge

**Forge** 是一个项目级 AI 操作系统 —— 为复杂项目（系统集成、等保合规、ITIL 运维）提供多 Agent 协作的智能执行引擎。

## 已实现功能

| 模块 | 说明 |
|------|------|
| **ProblemSolverAgent** | 问题类型判断（安全/ITIL/技术/混合）、Rule Pack 条款引用、ReAct + 结构化方案 |
| **ComplianceAgent** | 接收 ProblemSolver 结构化 handoff，多标准合规检查 |
| **SecurityAgent** | 等保2.0 安全诊断、配置建议、测评材料辅助 |
| **OperationsAgent** | ITIL/ISO20000 事件、变更、知识库建议 |
| **DocumentAgent** | 基于方案+合规结果自动生成 Markdown 资料 |
| **PMAdvisorAgent** | 项目经理视角总结、风险与行动项 |
| **Supervisor** | 智能路由、思考链路记录、Agent 协作编排 |
| **Rule Pack** | 等保 20 条 + ITIL 14 条 + 系统集成里程碑/文档清单 |
| **CLI Demo** | Rich 美化输出、`--type` / `--save` / `--load`、`--check-mode` / `--report`、满意度反馈 |
| **ToolRegistry** | 6 Agent 工具集统一注册（problem_solver … pm_advisor） |
| **Knowledge** | `utils/knowledge.py` 标签检索，ProblemSolver 注入 `prior_cases` |
| **配置** | `forge/config.py` + `.env` 多厂商 LLM |
| **Web API** | FastAPI `POST /solve`（雏形） |

## 标准流水线

```
接收问题 → Supervisor（意图路由 + 思考链路）
         → ProblemSolver（分类 + Rule Pack 引用）
         → (Security | Operations)*
         → Compliance（结构化 handoff 校验）
         → (合规重试 ≤2) → Document → PMAdvisor → Finalize
```

## 快速开始（虚拟环境）

```powershell
.\setup.ps1
copy .env.example .env
# 编辑 DEEPSEEK_API_KEY（可选，无 Key 使用启发式模式）

.\.venv\Scripts\python.exe -m pytest tests/ -q --ignore=tests/test_full_pipeline.py -k "not test_run_forge_cli_helper"
# 含端到端闭环（较慢）:
.\.venv\Scripts\python.exe -m pytest tests/test_full_pipeline.py -q
```

## CLI 用法

```powershell
# 直接输入问题
.\run.bat "等保三级登录401故障，请诊断"

# 按类型运行
.\run.bat --type security
.\run.bat --type itil
.\run.bat --type general

# 保存 / 加载
.\run.bat --type security --save
.\run.bat --load .forge_state/cli-demo.json "继续优化方案"

# 混合场景 / 交互式
.\run.bat --scenario mixed
.\run.bat -i

# 跳过满意度评分（CI/脚本）
.\run.bat --type general --no-feedback

# 合规严格度 + 运行报告
.\run.bat --type security --check-mode strict --report --no-feedback

# --type / --scenario 默认预置演示证据（文档+WBS+Rule Pack 关键词索引）
# 裸问题不加预置：.\run.bat "自定义问题"  或显式 --no-demo-seed
```

运行结束后（交互式终端）会提示 **1-5 分满意度**，写入 `knowledge_base` 供后续 Agent 参考。

## Demo 故事板（Rich，默认）

默认使用 Rich 分段展示完整流水线（`--plain` 回退 ANSI）：

| 区块 | 内容 |
|------|------|
| ① 用户问题 | 原始提问 |
| ② ProblemSolver | 方案、Rule Pack 引用、根因 |
| ③ Compliance | 状态/风险/缺口 + **合规重试时间线** |
| ④ Document | 生成资料列表 |
| ⑤ PM 顾问 | 行动项摘要 |
| 置信度分解 | 合规/证据/历史因子 → `auto_execute` / `needs_review` / `block` |
| ⑥ 执行任务 | 整改 WBS / 变更申请草稿（v1.1） |
| 审批流程 | 待审批项；`--auto-approve` 或恢复后 `--approve`/`--reject` |
| 运行统计 | 耗时、Agent 调用、Handoff、置信度 |

```powershell
.\run.bat --type security --no-feedback              # Rich Demo
.\run.bat --type security --plain --no-feedback      # ANSI 旧输出
.\run.bat --type security --auto-approve --no-feedback   # 半自治：自动审批执行
.\run.bat --type security --auto-approve --execution-mode local_manifest --no-feedback  # 写执行清单到 reports/execution/
.\run.bat --load .forge_state/cli-demo.json --approve "继续"  # 批准待审任务
```

### v1.1 执行后端与知识闭环

| 模式 | 说明 |
|------|------|
| `simulate`（默认） | 内存模拟执行，标记任务为 `executed` |
| `local_manifest` | 将 ready 任务写入 `reports/execution/exec_{run_id}_*.json`，供外部系统消费 |
| `webhook` | POST 到 `FORGE_EXECUTION_WEBHOOK_URL`（未配置时回退 simulate） |

每次运行 finalize 会将会话摘要写入 `knowledge_base` 并重建 `memory_graph`；后续 ProblemSolver 通过 `search_similar_cases` 注入历史案例，并影响置信度 `history_factor`。

归档样例报告见 [`reports/`](reports/) 目录。

## 知识库 CLI

```powershell
.\run.bat kb search --tag security
.\run.bat kb search --tag security --load-state .forge_state/cli-demo.json
```

## Makefile（Git Bash / WSL）

```bash
make setup
make test
make test-integration   # 全闭环 + v1.1 集成测试
make demo-security
make demo-itil
make demo-mixed
make report             # 生成 reports/latest-security.md
make test-llm           # 需配置 API Key；验证引用率 ≥70%
```

## Docker（可选）

```bash
cp .env.example .env   # 配置 API Key
docker compose up --build
# → http://127.0.0.1:8000/
```

## 开发路线图

五阶段详细计划与完成状态见 [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md) §22。  
新增 Agent 接入见 [`docs/AGENT_CHECKLIST.md`](docs/AGENT_CHECKLIST.md)。  
合规模式说明见 [`docs/COMPLIANCE_CHECK_MODE.md`](docs/COMPLIANCE_CHECK_MODE.md)。

CI 默认跑离线测试（`-m "not llm"`）；LLM 验收可在 GitHub Actions 手动触发 `workflow_dispatch` 并配置 `DEEPSEEK_API_KEY`。

## 配置（.env）

```env
FORGE_LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=sk-xxx
FORGE_LLM_MAX_RETRIES=3
```

支持 `deepseek` | `openai` | `aliyun` | `volcengine`，详见 `.env.example`。

## 架构（net-ops 风格）

```
Supervisor
  └── PipelineOrchestrator   # 问题分类 + 专家队列编排
        └── ProblemSolver → (Security|Operations)* → Compliance
              → Document → PMAdvisor → Execution → ApprovalGate → Finalize

AgentRegistry (core/agent_registry.py)   # 节点注册与 workflow 组装
ConfidenceScorer (core/confidence/)      # v1.1 置信度 → 审批门控

BaseAgent (core/base_agent.py)
  ├── run(state)             # 统一入口
  ├── get_tools()            # ToolRegistry
  └── run_react / invoke_structured  # utils/llm.py

ToolRegistry (core/tool_registry.py)
  └── 6 Agent 工具集（problem_solver, compliance, security, operations, document, pm_advisor）

详细架构与 v1.0 范围见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)、[docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md)。
```

## 项目结构

```
forge/
  agents/          # 各 Agent 实现（继承 BaseAgent）+ Pydantic 输出模型
  cli/             # parser、scenarios、runner、Rich/ANSI 展示
  config.py        # pydantic-settings 配置
  core/            # BaseAgent、ToolRegistry、Orchestrator、Supervisor、State
  prompts/         # Agent 提示词
  tools/           # 工具实现（经 ToolRegistry 挂载）
  utils/           # LLM、agent_context、conversation
rule_packs/        # 行业规则 JSON
tests/
```

## Web 服务

```powershell
.\run.bat --web
# http://127.0.0.1:8000/  POST /solve
```

## 开发说明

- 所有依赖安装在 `.venv/`，勿污染系统 Python
- Agent 输出统一继承 `AgentOutputBase`（`to_state_dict` / `to_display_json`）
- `conversation_history` 中 `event=thinking` 记录各 Agent 关键决策
- `agent_context` 在 Agent 间传递结构化 handoff（如 ProblemSolver → Compliance）
