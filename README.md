# Compound Marketplace

A Claude Code plugin marketplace featuring the **Compound Engineering Plugin** — tools that make each unit of engineering work easier than the last.

## Installation

### Claude Code

```bash
/plugin marketplace add Standard-Syntax/compound-engineering
/plugin install compound-engineering
```

After installation, restart Claude Code to load the new commands.

### Local Development

To test changes to the plugin locally without publishing:

```bash
alias claude-dev-ce='claude --plugin-dir /path/to/compound-engineering/plugins/compound-engineering'
```

Run `claude-dev-ce` instead of `claude` to test your modifications.

## Getting Started

The plugin follows a cyclical workflow. For new improvements, start with ideation. For bugs or known features, start with planning.

| Command | When to Use |
|---------|-------------|
| `/ce:ideate` | Discover what to work on — surfaces high-impact improvements |
| `/ce:brainstorm` | Clarify a vague idea before committing to a plan |
| `/ce:plan` | Turn a clear feature or fix into actionable steps |
| `/ce:work` | Execute the plan systematically |
| `/ce:review` | Catch issues before merging |
| `/ce:compound` | Document what was learned |

## Example Workflow: Adding a Feature

This example walks through adding a notification system to a project.

### 1. Ideate

```
/ce:ideate
```

The plugin surfaces improvement candidates, scores them by impact and effort, and filters through adversarial debate. Suppose it identifies "add user notification system" as the top-scored idea.

### 2. Brainstorm

```
/ce:brainstorm add user notification system
```

This clarifies the feature boundaries: push vs in-app, email vs SMS, user preferences, delivery guarantees. The output is a refined description ready for planning.

### 3. Plan

```
/ce:plan
```

When prompted, describe the feature: "Add a notification system that sends in-app and email alerts when users are mentioned or assigned."

The plan skill produces a structured implementation plan with phases, verification gates, and acceptance criteria.

### 4. Work

```
/ce:work
```

The work skill:
- Creates a feature branch
- Breaks the plan into tracked tasks
- Executes each phase with verification
- Opens a PR when complete

### 5. Review

```
/ce:review
```

Multi-agent review runs parallel checks for security, data integrity, performance, Python conventions, and agent-native parity. Issues are surfaced with fixes.

### 6. Compound

```
/ce:compound
```

Document the key decisions and patterns established: how notification routing works, why a queue-based approach was chosen over direct sending, any gotchas discovered.

This becomes searchable institutional knowledge for the next similar feature.

## Python Stack

The plugin ships with a Python work execution engine (`ce_engine/`) built on LangGraph and `langchain-anthropic`.

| Layer | Choice |
|-------|--------|
| Python | 3.13 |
| Package manager | `uv` |
| Lint | `ruff` |
| Type checker | `ty` |
| Data validation | Pydantic v2 |
| AI frameworks | LangGraph · langchain-anthropic |
| HTTP | `tenacity` (via langchain-anthropic client) |

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

## Quick Reference

| Task | Command |
|------|---------|
| Surface improvement ideas | `/ce:ideate` |
| Clarify requirements | `/ce:brainstorm <description>` |
| Create implementation plan | `/ce:plan` |
| Execute plan | `/ce:work` |
| Review code | `/ce:review` |
| Document learnings | `/ce:compound` |
| Stress-test a plan | `/deepen-plan` |
| Run full autonomous workflow | `/lfg` |

## Learn More

- [Plugin README](plugins/compound-engineering/README.md) - all 32 agents, 73 skills, MCP servers
- [ce_engine README](ce_engine/README.md) - Python LangGraph execution engine
- [Compound engineering: how Every codes with agents](https://every.to/chain-of-thought/compound-engineering-how-every-codes-with-agents)
- [The story behind compounding engineering](https://every.to/source-code/my-ai-had-already-fixed-the-code-before-i-saw-it)
