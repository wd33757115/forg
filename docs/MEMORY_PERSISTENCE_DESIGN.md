# Forge Memory & Persistence System — Grok-Inspired Design

**Date**: 2026-06-08  
**Status**: Starting implementation (post D1-D4 core capability work). Pivot from "ProblemSolver depth" to the next major legacy item: durable project memory + robust persistence.  
**Goal**: Turn Forge's current "knowledge_base list + stub graph + per-project JSON snapshot" into a first-class, cross-run, outcome-aware, project-scoped memory system that makes agents (especially ProblemSolver) truly "remember and learn" like a mature project AI OS — explicitly modeled on Grok-style memory principles.

## Why now? (Context from prior work)
- D1–D4 completed the "会思考 / 会用规则 / 会用经验" core for ProblemSolver (structured reasoning, rule causal quality, prior case injection with outcome bias, execution feedback closed-loop, classification self-adaptation + self-critique).
- Knowledge/memory was already partially exercised (search_similar_cases, format_memory_context, D3 execution learning, finalize → extract_reusable_knowledge → kb + memory_graph rebuild).
- But the foundation remains v1.0-scoped: in-memory during run, coarse file snapshots, no independent memory package, graph is rebuilt from scratch, many memory signals are reset on new runs, no episodic store, no clear write/consolidation abstraction, retrieval is heuristic only.
- Roadmaps (ARCHITECTURE.md, PHASED_ROADMAP.md, IMPLEMENTATION_PLAN.md) explicitly deferred "独立 memory/ 子系统 + 跨会话持久图谱 + 向量" to v2+.
- User request: "直接切到其他遗留大项，持久化，记忆系统的设计参考grok的记忆系统设计".

## Grok Memory Principles (adapted to Forge "Project AI OS")
Grok (xAI) memory for long-running helpful interactions emphasizes:
- **Persistent facts across sessions**, not raw chat dumps. Structured, queryable, user-inspectable.
- **Relational / entity memory**: things linked to other things (user ↔ preferences ↔ past events).
- **Outcome / utility weighted retrieval**: remember what was useful or what failed, so future decisions improve.
- **Write-back from real actions**: the system learns from what actually happened (tools called, results, human feedback).
- **Hybrid retrieval**: keyword + semantic + recency + importance.
- **Layers / scopes**: short-term working context vs long-term personal/project memory.
- **Auditability & control**: you can see/edit what is remembered.

**Forge mapping** (project instead of "user"):
- Project-scoped (per project_id), multi-run durable memory.
- Structured entries (KnowledgeEntry + richer episodic records) with outcome, related_rules, source_run, confidence, tags.
- Graph for relations (case → rule "references", case → execution "produced", run → decision, etc.) — we already have the seed in `core/memory/graph.py`.
- Heavy bias toward **positive/negative outcomes** in scoring (we enhanced this in D3 search_similar_cases + confidence factors).
- Write paths after Execution, Compliance, Finalize, Approvals (real "what happened").
- Layers:
  1. **Working memory** — current `ProjectState` (fast, LangGraph run scope, lots of last_* + messages + execution_results).
  2. **Episodic memory** — past runs/sessions as first-class records (what problem, what SolutionOutput + compliance + docs + execution outcomes + human approvals, full rationale).
  3. **Semantic / Case memory** — distilled reusable "what worked here" (the knowledge_base cases, extracted patterns, team habits).
  4. **Procedural / Rule memory** — links and application history (memory_graph edges + usage stats on rules).
- Future: vector embeddings for semantic similarity on top of the structured + graph base.
- Consolidation: turn a raw run (episodic) into 1–N high-signal case entries + graph updates (currently a weak version lives in `knowledge_extract.py`).
- Retrieval specialized for agents: ProblemSolver (prior_cases + execution lessons), Compliance (past similar failure patterns), PMAdvisor (recurring risks), Supervisor (routing hints from history?).

This directly advances the original "知识利用能力" (Category 3) and "置信度、风险评估与反馈" (Category 6) at the *system* level, not just inside one PS call.

## Current State (as of 2026-06-08 post-D4)
- **ProjectState** (forge/core/state.py): Excellent working memory shape. Includes `knowledge_base`, `memory_graph`, `execution_results`, `conversation_history`, last_* artifacts, etc. Many fields intentionally reset per-run via `prepare_state_for_run`.
- **Persistence** (forge/utils/state_persistence.py): Per-project JSON (`.forge_state/{project_id}.json`), versioned, message (de)serialization, `save/load/prepare/list`. Preserves kb/docs/wbs across runs; resets run-scoped outputs (including `memory_graph` — this is a key limiter today).
- **Knowledge append/search** (utils/knowledge.py): `append_knowledge`, `search_knowledge` (tags + agent + keyword simple overlap + outcome bonus). Used by finalize.
- **Similar case retrieval + graph** (utils/knowledge_memory.py + core/memory/graph.py): `search_similar_cases` (tag/keyword + rule graph boost via "references" edges + positive_outcome bonus + match_reason/score). `MemoryGraph` (Pydantic nodes/edges, `from_knowledge_entries`). Rebuilt wholesale on finalize.
- **Auto-extract** (utils/knowledge_extract.py): `extract_reusable_knowledge` at finalize → session_summary case + related_rules + outcome + rebuild graph patch. Good seed.
- **CLI** (cli/kb.py): basic `kb search --tag/--agent`.
- **Usage**: Primarily ProblemSolver (D1–D3 injection + D3 execution feedback). Some confidence factors read history. Not broadly used by other agents yet.
- **Gaps**:
  - No durable episodic store (past runs are only in full state snapshots or lost in reset).
  - memory_graph reset on prepare → cross-run "project brain" is fragile (only kb list survives reliably).
  - Full rebuild every time (no incremental).
  - No MemoryManager abstraction → logic scattered, hard to evolve backend.
  - No explicit consolidation step or importance scoring.
  - Execution results (key feedback) are transient.
  - Retrieval not yet exposed/pluggable for Compliance/PM/etc.
  - No vector layer (deferred, as planned).
  - Persistence is "whole state" snapshot, not memory-event log (harder to query/compact/audit at scale).

## Target Architecture (Grok-inspired, incremental)
```
Project Memory (per project_id, durable)
├── Episodic Store (runs / sessions)
│   └── run_id, timestamp, problem, solution (full or summary), compliance, execution_results, approvals, trace refs, outcome
├── Semantic / Case Store (knowledge_base evolution)
│   └── distilled entries (type=case|pattern|fact|risk, outcome, related_rules, tags, source_run, confidence, usage_count)
├── Graph (relations)
│   └── nodes (case|rule|document|execution|fact), edges (references, produced_by, led_to, similar_to, supersedes)
├── (Future) Embeddings / Vector index (per-case content for semantic search)
└── Access Layer
    ├── MemoryManager / ProjectMemory (append, search_similar, get_episodes, consolidate_run, rebuild_graph, to_state_patch)
    ├── Retrieval helpers (search_similar_cases enhanced, search_by_rule, search_by_outcome, get_project_facts)
    └── Persistence backend (FileJSONL today, SQLite later, pluggable)
```

**Integration points**:
- On state prepare/load: MemoryManager loads/merges durable memory into working ProjectState (kb + graph + optionally recent episodes).
- After key events: Execution (results + outcome), Compliance (failure patterns), Finalize (solution + compliance + docs), Approval (human signal) → write episodic + distill to cases + update graph.
- At decision time: PS (already strong), Compliance (learn from past similar non-compliance), PMAdvisor (recurring risks/patterns), Supervisor (perhaps de-risk routing using history).
- On save: persist the memory view (or event log) alongside/inside the state JSON (or separate files for queryability).
- CLI / tools: `kb` extended to inspect episodes, facts, graph; perhaps "memory consolidate".

**Persistence evolution**:
- P0 (now): Keep JSON state snapshots as primary. Make memory_graph durable (stop resetting it, merge on load). Add lightweight episodic append inside the state (or sidecar JSONL). Manager that owns read/write.
- P1: Separate memory files (knowledge.jsonl, episodes.jsonl, graph.json) under .forge_state/{project}/ for efficient append + partial load. Atomic writes.
- P2: SQLite (or Postgres) with tables for entries/edges/runs + simple FTS or future vector.
- Always: project_id scoping, timestamps, source provenance, backward compat.

**Non-goals for first cut**:
- Full vector embeddings (keep heuristic + graph strong; add later).
- Global cross-project memory (strictly per-project unless explicit sharing added).
- Heavy compaction / forgetting (simple recency + outcome weighting first).
- Real-time sync / multi-writer concurrency (single-agent-run model for now).

## Phased Plan (similar to D1–D4 style)
**M0 (this session — foundation + quick wins)**:
- Design doc (this file).
- Introduce `forge/core/memory/manager.py` (ProjectMemory class or MemoryManager facade) that:
  - Wraps/owns kb + graph.
  - Provides `append_case(...)`, `append_execution_result(...)`, `search_similar(...)` (thin over existing + future), `consolidate_from_state(...)`, `to_graph_patch()`, `recent_episodes(limit)`.
- Update `state_persistence.py`:
  - Remove or conditionalize `memory_graph` from _RUN_RESET_FIELDS (carry durable graph; rebuild from kb only if absent/mismatched).
  - Add `merge_memory_on_prepare` or equivalent.
  - Ensure `prepare_state_for_run` can inject recent memory context.
- Strengthen the finalize write path (already good) and add one more: execution results → memory (so D3 closed loop survives across runs).
- Make `search_similar_cases` and `extract_reusable_knowledge` optionally delegate to a manager.
- Update a couple call sites (supervisor finalize, execution if appropriate).
- Add 2–3 targeted tests (cross-run memory carry + retrieval, graph persistence, episodic write).
- Run PS tests + core_capability eval + quick broader non-llm tests (ensure no regression on existing D1–D4 behavior).
- Update docs: PHASED_ROADMAP (mark Stage 4 deepening started), CORE_CAPABILITY_SCORECARD (add memory section), this design, brief note in PROBLEM_SOLVER_DEPTH_PLAN if relevant.

**M1 (next)**:
- Episodic records as first-class (lightweight run log persisted separately or in state).
- Broader write hooks (Compliance failures, Approval outcomes).
- Manager used by at least one non-PS agent (e.g. PMAdvisor or Compliance for pattern lookup).
- Basic compaction or "memory health" summary.
- CLI `kb` enhancements (list episodes, show graph stats).

**M2+**:
- Pluggable backend (File → SQLite).
- Vector index (Chroma or local) + hybrid search (heuristic + semantic).
- Importance / decay scoring.
- Cross-agent memory APIs + Supervisor routing hints from memory.
- Project memory dashboard / inspection in demo/report.

## Risks & Constraints
- Must not break existing persistence contracts or D1–D4 PS behavior (knowledge injection, execution feedback within a prepared state, PS-CLS-01 etc. gates).
- Keep offline/heuristic paths working (no hard dependency on external vector DB).
- State remains the "working" contract for LangGraph; memory is the durable long-term layer that seeds/enriches state.
- Audit: every memory write should be traceable to a run_id + agent.

## Success Metrics (initial)
- A saved project state + reload + new run can retrieve prior cases via search_similar_cases with the memory_graph boost intact (no data loss on memory_graph).
- Execution results from a prior run can influence a subsequent PS run's reasoning (D3 closed loop now durable).
- New memory writes (cases + graph updates) are observable via `kb search` and in saved JSON.
- No regression on 240+ tests, core eval offline gate, and existing PS depth behaviors.
- Clear extension points for M1 episodic + later vector.

This work directly makes the "project brain" real and durable — the missing piece for Forge to feel like a true long-running AI operating system for projects, in the spirit of how Grok maintains useful memory across interactions.

Next steps in code: implement M0 manager + persistence hardening + hooks. All changes will be incremental and tested.