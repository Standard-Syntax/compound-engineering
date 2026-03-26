---
date: 2026-03-26
topic: context-engineering-refactor-requirements
---

# Context Engineering Refactor

## Problem Frame

The compound-engineering plugin lacks the **context management primitives** that HumanLayer's "Frequent Intentional Compaction" (FIC) methodology treats as first-class concerns. LLMs are stateless functions — the only lever is the quality of what is in the context window. The plugin's workflows currently do not manage context utilization, do not separate research from planning, and do not compact artifacts between phases. This causes plans to operate on partial/noisy codebase understanding, context to fill with search/read noise during implementation, and the highest-leverage artifact (research) to be discarded after each session.

## Requirements

### Research Phase

- R1. A new `ce:research` skill produces a standalone, compacted research artifact written to `docs/research/YYYY-MM-DD-description.md` with YAML frontmatter (date, topic, tags, status, git_commit, branch)
- R2. The skill spawns parallel sub-agents (repo-research-analyst, framework-docs-researcher, best-practices-researcher, git-history-analyzer) and instructs them to document what IS, not what SHOULD BE
- R3. Research artifacts include file:line references and a structured layout (Research Question, Summary, Detailed Findings, Architecture Documentation, Code References)
- R4. Research artifacts end with a developer prompt: "Please review this research before proceeding to planning. A misunderstanding here cascades into the plan and implementation."

### Planning Phase

- R5. `ce:plan` accepts an optional research artifact path as input; if provided, skips inline research and uses the artifact instead
- R6. `ce:plan` searches `docs/research/` for existing relevant artifacts before spawning new research agents
- R7. All plan templates include a required `## What We're NOT Doing` section listing out-of-scope items
- R8. All plan templates separate success criteria into `#### Automated Verification` (agent-runnable commands) and `#### Manual Verification` (human-gated checks)
- R9. Plan output includes a quality cascade warning: "A mistake in the plan leads to 100s of bad lines of code. A mistake in the research leads to 1000s."

### Work Phase

- R10. `ce:work` pauses between phases for manual verification when the plan has Manual Verification items, using a structured pause format
- R11. `ce:work` writes structured progress summaries to the plan file after each phase (check off completed items, note current status, blockers, key decisions)
- R12. `ce:work` instructs the agent to prefer sub-agents for noisy operations and to compact if more than 15 files have been read directly
- R13. `ce:work` keeps context focused on the current phase; no pre-loading of files for future phases

### Compound Phase

- R14. `ce:compound` checks for an associated research artifact in `docs/research/` and cross-references it in the solution doc when one exists
- R15. `ce:compound` captures research corrections (misconceptions or incorrect assumptions corrected during implementation) as learnings to prevent future research from making the same mistakes

### Compact Utility

- R16. A new `ce:compact` skill produces a structured compaction summary written to `.context/compound-engineering/compact-TIMESTAMP.md`
- R17. Compaction output format includes: Goal, Approach, Completed Steps, Current Status, Relevant Files, Key Decisions, Next Steps
- R18. `ce:compact` is standalone and usable at any point in any workflow without being tied to a specific step

## Success Criteria

- Research artifacts are discoverable in `docs/research/` by topic and date
- Plans with research input produce better-scoped, more accurate plans than plans without research
- Work execution pauses at manual verification gates and does not skip them
- Context utilization stays in the 40-60% range during complex implementations through compaction
- Solution docs reference their source research artifacts
- Compaction artifacts are sufficient to resume work in a new context window

## Scope Boundaries

- CLI converter logic (`ce_engine/src/`) is out of scope
- Cross-platform sync, MCP servers, and CI are out of scope
- Changes are limited to skills, commands, and agent prompts within `plugins/compound-engineering/`

## Key Decisions

- **Research is a prerequisite for planning, not part of it**: Separating research into its own phase prevents context pollution before planning begins. This follows HumanLayer's pattern of starting a new context window for planning with only the compacted research document as input.
- **Sub-agents are for context control, not role-playing**: When spawning sub-agents, the goal is keeping the parent's context clean. Agents are named by function (e.g., "context-analyzer"), not persona.
- **Compaction = structured summary written to disk**: Compaction is not just remembering — it produces a file that another context window can cold-start from.
- **Human review belongs upstream of code**: The review command handles code with 14 agents. Human effort belongs on research and plans, not implementation.
- **Rollout order is 1 → 2 → 3 → 4 → 5**: Each phase is independently valuable but builds on the previous one. Phase 1 enables everything downstream.

## Dependencies / Assumptions

- `docs/research/` directory convention must be created before Phase 1 ships
- The existing research agents (repo-research-analyst, framework-docs-researcher, best-practices-researcher) are assumed to exist and be functional; no new agents need to be authored for Phase 1
- The `git-history-analyzer` agent already exists at `compound-engineering:research:git-history-analyzer`
- `ce:work` currently delegates to a LangGraph engine; Phase 3 modifications must be compatible with that architecture

## Outstanding Questions

### Resolve Before Planning

- None — all 7 gaps are well-characterized and the implementation approach for each phase is defined.

### Deferred to Planning

- **[Technical]** `ce:work` LangGraph engine integration: Phase 3 adds human verification gates and compaction to the work execution. Need to determine whether these modifications belong in the LangGraph engine itself or in the `ce-work` skill wrapper.
- **[Technical]** Context budget trigger threshold: The plan suggests "15 files read directly" as a compaction trigger. Validate whether this is the right threshold or if it should be adjustable per-skill.
- **[Needs research]** `docs/research/` naming: The plan uses `YYYY-MM-DD-description.md`. Should there be an automatic slug/sequence convention (like plans use with `001`, `002`) when multiple research sessions happen on the same topic on the same day?

## Next Steps

→ `/ce:plan` for structured implementation planning
