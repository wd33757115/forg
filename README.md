# Forge

**Forge** 是一个项目级 AI 操作系统 —— 为复杂项目（系统集成、等保合规、ITIL 运维）提供多 Agent 协作的智能执行引擎。

## 已实现功能

| 模块 | 说明 |
|------|------|
| **ProblemSolverAgent** | ReAct + 结构化输出，问题诊断与多方案推荐 |
| **ComplianceAgent** | 多标准合规检查（base_si / 等保2.0 / ITIL） |
| **DocumentAgent** | 基于方案+合规结果自动生成 5 类 Markdown 资料 |
| **Supervisor 闭环** | ProblemSolver → Compliance → (重试≤2次) → Document → Finalize |
| **Rule Pack** | 可加载的行业规则包（等保、ITIL、系统集成） |
| **ProjectState** | 持久化项目记忆、conversation_history、final_output |
| **CLI Demo** | 交互式命令行，漂亮打印完整执行结果 |

## 快速开始

```bash
# 1. 安装
pip install -e .

# 2. 配置 API Key（可选，无 Key 时使用规则引擎）
cp .env.example .env
# 编辑 .env: DEEPSEEK_API_KEY=sk-your-key

# 3. 运行 Demo（Windows 请用 py 或 .\run.bat，勿用 Store 占位符 python）
py main.py                          # 默认示例问题
py main.py -i                         # 交互式选择
py main.py --example 2                # ITIL 事件示例
py main.py "等保三级登录401故障" -v    # 自定义问题 + 详细日志
py main.py --show-docs                # 显示完整生成资料

# 或双击 / 命令行: .\run.bat --example 2
```

> **Windows 提示**：若 `python main.py` 无任何输出即返回，说明 `python` 指向
> `WindowsApps\python.exe`（微软商店占位符）。请改用 `py main.py`、`.\\run.bat`，
> 或在「设置 → 应用 → 应用执行别名」中关闭 `python.exe` / `python3.exe` 别名。

## 示例问题

```bash
# 等保相关
py main.py "等保三级系统登录认证失败，请诊断并生成整改资料"

# ITIL 事件
py main.py "ITIL事件：核心交换机故障导致业务中断，请分析根因"

# 技术故障
py main.py "数据库连接池耗尽导致接口超时，请给出合规解决方案"
```

## 输出内容

Demo 运行后会打印：

1. **问题分析** — ProblemSolver 根因分析
2. **推荐方案** — 方案 ID、实施路径、等保/ITIL 影响
3. **合规检查结果** — 三模块得分、缺口、整改建议、重试次数
4. **生成资料列表** — 整改方案、等保记录、ITIL 事件/问题、变更申请
5. **Agent 交互时间线** — conversation_history 完整记录

## Rule Pack

```
rule_packs/
├── system_integration_v1.json   # 完整规则包（base_si + 等保 + ITIL）
├── dengbao_level3_sample.json     # 等保三级 8 项精选检查项
└── itil_basic_sample.json         # ITIL 4 基础 8 项实践
```

## 项目结构

```
forge/
├── core/           # State, Rule Pack, Supervisor, Workflow
├── agents/         # ProblemSolver, Compliance, Document
├── tools/          # Agent 工具集
├── prompts/        # Agent 提示词
├── utils/          # 日志、环境变量、对话记录
└── main.py         # CLI Demo 入口
main.py             # 项目根入口（转发到 forge.main）
rule_packs/         # Rule Pack JSON 定义
tests/              # 测试套件
```

## 运行测试

```bash
py -m pytest tests/ -q
```

## 环境变量

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥（可选） |
| `FORGE_LOG_LEVEL` | 日志级别：DEBUG / INFO / WARNING |
| `NO_COLOR` | 设置任意值禁用 CLI 颜色 |

## 技术栈

- Python 3.11+
- LangGraph + LangChain
- Pydantic v2
- DeepSeek API（OpenAI 兼容）
