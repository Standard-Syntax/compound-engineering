# Compound Marketplace

[![Build Status](https://github.com/EveryInc/compound-engineering-plugin/actions/workflows/ci.yml/badge.svg)](https://github.com/EveryInc/compound-engineering-plugin/actions/workflows/ci.yml)
[![npm](https://img.shields.io/npm/v/@every-env/compound-plugin)](https://www.npmjs.com/package/@every-env/compound-plugin)

A Claude Code plugin marketplace featuring the **Compound Engineering Plugin** — tools that make each unit of engineering work easier than the last.

## Claude Code Install

```bash
/plugin marketplace add EveryInc/compound-engineering-plugin
/plugin install compound-engineering
```

## Python Stack

The plugin ships with a Python work execution engine (`ce_engine/`) built on LangGraph and PydanticAI.

| Layer | Choice |
|-------|--------|
| Python | 3.13 |
| Package manager | `uv` |
| Lint | `ruff` |
| Type checker | `ty` |
| Data validation | Pydantic v2 |
| AI frameworks | LangGraph · PydanticAI · Anthropic SDK |
| HTTP | `httpx` + `tenacity` |

```bash
cd ce_engine
uv sync
uv run ruff check src/
uv run ty check src/
```

## Workflow

```
Brainstorm → Plan → Work → Review → Compound → Repeat
    ↑
  Ideate (optional — when you need ideas)
```

| Command | Purpose |
|---------|---------|
| `/ce:ideate` | Discover high-impact project improvements through divergent ideation and adversarial filtering |
| `/ce:brainstorm` | Explore requirements and approaches before planning |
| `/ce:plan` | Turn feature ideas into detailed implementation plans |
| `/ce:work` | Execute plans with worktrees and task tracking |
| `/ce:review` | Multi-agent code review before merging |
| `/ce:compound` | Document learnings to make future work easier |

The `/ce:ideate` skill proactively surfaces strong improvement ideas, and `/ce:brainstorm` then clarifies the selected one before committing to a plan.

Each cycle compounds: brainstorms sharpen plans, plans inform future plans, reviews catch more issues, patterns get documented.

> **Beta:** Experimental versions of `/ce:plan` and `/deepen-plan` are available as `/ce:plan-beta` and `/deepen-plan-beta`. See the [plugin README](plugins/compound-engineering/README.md#beta-skills) for details.

## Philosophy

**Each unit of engineering work should make subsequent units easier—not harder.**

Traditional development accumulates technical debt. Every feature adds complexity. The codebase becomes harder to work with over time.

Compound engineering inverts this. 80% is in planning and review, 20% is in execution:
- Plan thoroughly before writing code
- Review to catch issues and capture learnings
- Codify knowledge so it's reusable
- Keep quality high so future changes are easy

## Learn More

- [Full component reference](plugins/compound-engineering/README.md) - all agents, commands, skills
- [Compound engineering: how Every codes with agents](https://every.to/chain-of-thought/compound-engineering-how-every-codes-with-agents)
- [The story behind compounding engineering](https://every.to/source-code/my-ai-had-already-fixed-the-code-before-i-saw-it)
