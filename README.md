# Forge

**Forge** 是一个项目级 AI 操作系统 —— 为复杂项目（系统集成、等保合规、ITIL 运维）提供多 Agent 协作的智能执行引擎。

## 已实现功能

| 模块 | 说明 |
|------|------|
| **ProblemSolverAgent** | ReAct + 结构化输出，问题诊断与多方案推荐 |
| **ComplianceAgent** | 多标准合规检查（base_si / 等保2.0 / ITIL） |
| **SecurityAgent** | 等保2.0 安全诊断、配置建议、测评材料辅助 |
| **OperationsAgent** | ITIL/ISO20000 事件、变更、知识库建议 |
| **DocumentAgent** | 基于方案+合规结果自动生成 5 类 Markdown 资料 |
| **PMAdvisorAgent** | 项目经理视角总结、风险与行动项 |
| **Supervisor 流水线** | ProblemSolver → Security/Ops → Compliance → Document → PM |
| **Rule Pack** | 可加载的行业规则包（等保、ITIL、系统集成） |
| **ProjectState** | 持久化项目记忆、conversation_history、pipeline_trace |
| **CLI Demo** | 交互式命令行，场景选择，状态保存/恢复 |
| **Web API** | FastAPI 服务，`POST /solve` 运行完整流程 |

## 标准流水线

```
接收问题 → ProblemSolver → (Security | Operations)* → Compliance
         → (合规重试 ≤2) → Document → PMAdvisor → Finalize
```

## 快速开始（必须使用虚拟环境）

**不要把依赖装进系统 Python。** 项目自带脚本，所有包装在 `.venv/` 里：

```powershell
# 1. 一键创建 venv + 安装依赖（仅写入 .venv/，不动全局环境）
.\setup.ps1
# 或: setup.bat

# 2. 激活虚拟环境（可选，run.bat 会自动用 .venv）
.\.venv\Scripts\Activate.ps1

# 3. 配置 API Key（可选，无 Key 时使用规则引擎）
copy .env.example .env
# 编辑 .env: DEEPSEEK_API_KEY=sk-your-key

# 4. 运行测试（在 venv 内）
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

> 若 pip 镜像报错，setup 脚本默认使用 `https://pypi.org/simple`。

## CLI Demo

先执行 `.\setup.ps1`，之后用 `.\run.bat` / `.\run.ps1`（自动走 `.venv`，勿用全局 `pip` / `python`）。

```bash
# 场景演示
.\run.bat --scenario security      # 等保/安全问题
.\run.bat --scenario operations    # ITIL/运维事件
.\run.bat --scenario general       # 通用技术问题

# 交互式 / 自定义
.\run.bat -i
.\run.bat "等保三级登录401故障" -v

# 状态持久化
.\run.bat --scenario security --save-state
.\run.bat --resume "新的问题描述"
.\run.bat --list-states
```

## Web 服务

```bash
.\run.bat --web
# 或（venv 已激活时）
uvicorn web.app:app --reload --host 127.0.0.1 --port 8000
```

访问：

- 首页：http://127.0.0.1:8000/
- API 文档：http://127.0.0.1:8000/docs
- 健康检查：`GET /health`
- 求解接口：`POST /solve`

```bash
curl -X POST http://127.0.0.1:8000/solve \
  -H "Content-Type: application/json" \
  -d '{"question": "等保三级登录401故障，请诊断", "scenario": "security"}'
```

## 项目结构

```
forge/
├── core/           # State, Rule Pack, Supervisor, Workflow, Pipeline
├── agents/         # 全部 Specialist Agents + Pydantic 输出模型
├── tools/          # Agent 工具集
├── prompts/        # Agent 提示词
├── utils/          # 日志、持久化、Agent 安全包装
└── main.py         # CLI 入口
web/
├── app.py          # FastAPI 应用
└── models.py       # API 请求/响应模型
main.py             # 根入口（转发 CLI）
rule_packs/         # Rule Pack JSON
tests/              # 测试套件
requirements.txt    # 依赖清单
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥（可选） |
| `FORGE_LOG_LEVEL` | 日志级别：DEBUG / INFO / WARNING |
| `FORGE_WEB_HOST` | Web 服务地址（默认 127.0.0.1） |
| `FORGE_WEB_PORT` | Web 服务端口（默认 8000） |
| `NO_COLOR` | 设置任意值禁用 CLI 颜色 |

## 依赖版本说明

`requirements.txt` 里写的是 **最低兼容版本**（`>=`），不是锁死在旧版：

| 包 | 约束 | 说明 |
|----|------|------|
| langgraph | `>=1.0.0,<2.0` | 早期写的 `>=0.2.0` 只是下限过低；当前 PyPI 稳定版为 **1.2.x**，pip 会装最新 1.x |
| 其他 | `>=x.y` | 同样表示「至少该版本」，安装时取满足条件的最新版 |

查看 venv 内实际版本：`.venv\Scripts\pip.exe show langgraph`

## 技术栈

- Python 3.11+
- LangGraph 1.x + LangChain
- Pydantic v2
- FastAPI + Uvicorn
- DeepSeek API（OpenAI 兼容）

## 后续开发方向

- Web UI 前端（表单提交 + 结果可视化）
- python-docx 导出整改/测评 Word 文档
- 向量库持久化 Project Brain
- 更多 Rule Pack 行业模块
- 认证与多租户项目隔离
