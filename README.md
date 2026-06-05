# Forge

**Forge** is a project-level AI operating system — not a chatbot or traditional PM tool, but a persistent, multi-agent execution brain for complex projects.

## Phase 1 Foundation

This repository establishes the core foundation:

- **ProjectState** — typed project memory shared across agents
- **Rule Pack** — loadable industry rules (系统集成 / 等保2.0 / ITIL-ISO20000)
- **Supervisor** — routing hub for the agent graph
- **LangGraph workflow** — minimal runnable graph

## Quick Start

```bash
pip install -e .
cp .env.example .env   # add your DEEPSEEK_API_KEY
python -m forge.examples.run_basic
```

### DeepSeek API

Forge uses [DeepSeek](https://api.deepseek.com) via OpenAI-compatible API. Set in `.env`:

```
DEEPSEEK_API_KEY=sk-your-key-here
```

Without a key, agents fall back to rule-based heuristics.

## Structure

```
forge/
├── core/           # State, Rule Pack, Supervisor, workflow
├── agents/         # Specialized agents (stubs for Phase 2)
├── prompts/        # Agent prompt templates
├── tools/          # Agent tools
├── utils/          # Shared utilities
rule_packs/         # Bundled Rule Pack JSON (project root)
└── system_integration_v1.json
```

## Vision

See the product manifesto in project discussions. Forge evolves from **strong assistance** → **semi-autonomous execution** → **project OS**.
