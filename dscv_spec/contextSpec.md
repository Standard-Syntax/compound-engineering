# Compound Engineering × Advanced Context Engineering: Gap Analysis & Refactor Plan

**Date**: 2026-03-26
**Author**: Derek (via Claude analysis)
**Sources studied**:

- `Standard-Syntax/compound-engineering` (fork of `EveryInc/compound-engineering-plugin`)
- HumanLayer blog: “Advanced Context Engineering for Coding Agents” (Dex Horthy, Aug 2025)
- HumanLayer repo: `humanlayer/humanlayer` — `research_codebase.md`, `create_plan.md`, `implement_plan.md`

-----

## Executive Summary

Compound Engineering (CE) and HumanLayer’s “Frequent Intentional Compaction” workflow solve the same problem from different angles. CE emphasizes the *compounding loop* — plan, work, review, compound — where learnings accumulate across cycles. HumanLayer emphasizes *context hygiene within a single cycle* — research, plan, implement — where each step produces a compacted markdown artifact that keeps the context window lean and grounded.

CE is strong on breadth (25+ review agents, multi-tool orchestration, cross-IDE sync). HumanLayer is strong on depth (context utilization discipline, specialized sub-agents for codebase mapping, persistent research artifacts, human-review gates at high-leverage points).

The refactor adds HumanLayer’s depth to CE’s breadth. Ten gaps identified, seven recommended for implementation.

-----

## Gap Analysis

### Gap 1: No Dedicated Research Phase (HIGH IMPACT)

**What CE does now**: The workflow starts at brainstorm (requirements exploration) or jumps straight to plan. The `repo-research-analyst` and `best-practices-researcher` agents exist, but they are invoked *within* the plan step, not as a standalone phase that produces a reviewable artifact.

**What HumanLayer does**: A standalone `/research_codebase` command spawns parallel specialized sub-agents (codebase-locator, codebase-analyzer, codebase-pattern-finder, thoughts-locator), synthesizes findings, and writes a timestamped research document with frontmatter, file:line references, and architectural documentation. The research is pure documentation — “document what IS, not what SHOULD BE.”

**What this closes**: The blog demonstrated that plans built on research fixed a bug in the *correct* location within a 300k LOC Rust codebase, while plans without research attempted a different (worse) fix. Research grounds the agent in reality before it starts making decisions.

**Impact on CE commands**:

- **Plan**: Plans become grounded in verified codebase understanding. The `ce:plan` command can accept a research doc path, pre-loading its context.
- **Work**: Implementation agents inherit the right file paths and patterns from research, reducing file-search noise in the context window.
- **Review**: Reviewers can cross-reference the research doc to verify the implementation matches the intended approach.
- **Compound**: Research docs become institutional knowledge — a future developer running `/ce:plan` on a similar area gets a head start.

-----

### Gap 2: No Context Utilization Awareness (MEDIUM IMPACT)

**What CE does now**: No mechanism to monitor or manage context window usage. The `/lfg` command chains plan → deepen → work → review → resolve → test → video in a single session.

**What HumanLayer does**: Explicitly targets 40–60% context utilization. The entire workflow is designed around compaction checkpoints — each step produces a markdown artifact, the session is refreshed, and the next step starts with a clean context plus only the compacted artifact.

**What this closes**: In complex brownfield codebases, CE’s chained `/lfg` workflow will fill the context window during the plan phase, degrading quality in subsequent work and review phases. HumanLayer’s approach keeps each phase operating in a fresh, focused context.

**Impact on CE commands**:

- **Plan**: Add a compaction checkpoint after plan generation — write the plan, end the session, start fresh for work.
- **Work**: Add compaction after each implementation phase — update the plan file with status, refresh context, resume.
- **Compound**: This is a workflow-level change, not a single-command change. The `/lfg` orchestrator needs session boundaries.

-----

### Gap 3: No Persistent Research/Thoughts Directory (HIGH IMPACT)

**What CE does now**: Plans go to `docs/plans/`, learnings go to `docs/solutions/`. No dedicated research artifact store. No structured naming convention with dates and ticket references.

**What HumanLayer does**: Uses `thoughts/shared/research/YYYY-MM-DD-ENG-XXXX-description.md` with YAML frontmatter (date, researcher, git commit, branch, tags, status). Research docs are synced, searchable, and referenced by plan docs. A `thoughts-locator` agent exists specifically to discover prior research on a topic.

**What this closes**: Without persistent research, every new task starts from scratch. Prior codebase investigations are lost. The same files get re-read, the same architectural patterns get re-discovered. This directly contradicts CE’s core philosophy — each unit of work should make subsequent units easier.

**Impact on CE commands**:

- **Plan**: Before planning, the agent searches existing research docs for the relevant codebase area. Existing research eliminates redundant investigation.
- **Review**: Reviewers can verify implementation against the research that informed it.
- **Compound**: Research artifacts compound naturally — future research on the same area starts from the prior doc, updating rather than recreating.

-----

### Gap 4: Research Doesn’t Feed Into Plan (HIGH IMPACT)

**What CE does now**: `/ce:plan` gathers its own context. It may use the `learnings-researcher` agent to check prior compound docs, but there is no explicit “read the research document first” step.

**What HumanLayer does**: The `/create_plan` command accepts a research doc path as a parameter. It reads the doc fully before spawning any sub-agents. The plan template includes a “Current State Analysis” section that maps directly to research findings with file:line references.

**What this closes**: Plans grounded in research include correct file paths, real function signatures, and actual test conventions. Plans without research include guesses that the implementation agent must correct at execution time — burning context and introducing drift.

**Impact on CE commands**:

- **Plan**: Add an optional `--research` flag or parameter. If provided, read the research doc first and reference it in the plan. If not provided, warn the user and offer to run research first.
- **Work**: Inherits better file references and test patterns from research-grounded plans.

-----

### Gap 5: No Phase-by-Phase Compaction During Implementation (MEDIUM IMPACT)

**What CE does now**: `/ce:work` executes plan items with worktrees and task tracking. There is no explicit compaction between phases.

**What HumanLayer does**: For complex work, the implementer compacts the current status back into the plan file after each phase is verified. The plan file becomes a living progress document. If the context fills up, the agent refreshes and picks up from the last checkmark.

**What this closes**: Long implementations (3+ phases) will exhaust the context window. The agent loses sight of the overall plan, starts making decisions inconsistent with earlier phases, or forgets constraints established in research. Compaction after each phase prevents this.

**Impact on CE commands**:

- **Work**: After each phase’s automated verification passes, update the plan file with checkmarks and a brief status note. If the plan is large, offer to compact and restart.

-----

### Gap 6: No Automated vs. Manual Verification Split (MEDIUM IMPACT)

**What CE does now**: `/ce:review` runs multi-agent code review. The plan template likely includes success criteria, but there is no structural separation between “what the agent can verify” and “what requires human eyes.”

**What HumanLayer does**: Every plan phase has two sub-sections under “Success Criteria”: Automated Verification (commands to run) and Manual Verification (UI checks, performance under load, edge cases). After automated checks pass, the implementation agent pauses and asks the human to verify manual items before proceeding.

**What this closes**: Without this split, either (a) the agent runs autonomously and skips manual checks, shipping subtle UI bugs, or (b) the human has to figure out what needs manual testing by reading the whole plan. The split makes the human review gate explicit and efficient.

**Impact on CE commands**:

- **Plan**: Add Automated / Manual sections to the plan template.
- **Work**: After each phase, run automated verification, then pause for manual confirmation before proceeding.

-----

### Gap 7: Human Leverage Hierarchy Not Encoded (HIGH IMPACT)

**What CE does now**: The `/lfg` command runs the full pipeline autonomously. The philosophy is “80% planning and review, 20% execution,” but the tooling allows the entire chain to run without human intervention.

**What HumanLayer does**: Encodes a leverage hierarchy: bad research → thousands of bad lines of code. Bad plan → hundreds. Bad code → one bad line. Human review is mandatory between research→plan and plan→implement. The implementation prompt explicitly pauses for human review between phases.

**What this closes**: The blog recounts throwing out an entire research doc because Claude concluded the bug was invalid. If that research had flowed directly into a plan and implementation, the result would have been a PR that “fixes” a non-bug. The human gate caught the error at the highest-leverage point.

**Impact on CE commands**:

- **Plan**: After research, present findings to the human for validation before generating the plan.
- **Work**: After the plan is written, require explicit human approval before starting implementation.
- **Review**: Already strong — this is where CE excels.
- **Compound**: The `/lfg` fully-autonomous mode should be reframed as the exception, not the default. Consider a `/ce:guided` mode that pauses at each gate.

-----

### Gap 8: No “What We’re NOT Doing” in Plan Template (LOW IMPACT, EASY WIN)

**What CE does now**: Plan template focuses on what to build. No explicit out-of-scope section.

**What HumanLayer does**: Plan template includes “What We’re NOT Doing” — a list of explicitly out-of-scope items.

**What this closes**: Agentic coding is prone to scope creep. The agent encounters a related issue during implementation and “helpfully” fixes it, introducing untested changes. An explicit exclusion list gives the implementation agent a hard boundary.

**Impact on CE commands**:

- **Plan**: Add the section to the plan template. Two lines of change, high value.

-----

### Gap 9: Sub-Agent Specialization for Research (MEDIUM IMPACT)

**What CE does now**: Has `repo-research-analyst`, `best-practices-researcher`, `git-history-analyzer`, `learnings-researcher` — generic research agents.

**What HumanLayer does**: Has tightly scoped agents: `codebase-locator` (WHERE things are), `codebase-analyzer` (HOW things work), `codebase-pattern-finder` (find examples of patterns). Each agent has a single job and returns specific file:line references. They are documentarians, not evaluators.

**What this closes**: Generic research agents try to do everything in one pass — find files, understand code, suggest improvements. This floods their context window with noise. Specialized agents do one thing well in a clean context and return structured, compact results.

**Impact on CE commands**:

- **Plan**: Research sub-agents return better-structured input for planning.
- **Review**: Pattern-finder agents could be used during review to verify the implementation follows codebase conventions.

-----

### Gap 10: No “Desired End State” Specification in Plans (LOW IMPACT, EASY WIN)

**What CE does now**: Plans describe what to build and how to build it.

**What HumanLayer does**: Plan template includes “Desired End State” — a specification of what the system should look like after implementation, and how to verify it.

**What this closes**: Without a clear end-state specification, the implementation agent makes incremental decisions about “done” at each phase. The end result may satisfy each phase’s criteria while missing the overall goal. The end-state section gives the agent a north star.

**Impact on CE commands**:

- **Plan**: Add the section to the plan template. Easy change, moderate value.

-----

## Efficiency Impact Summary

|Gap                            |Phase Affected|Efficiency Gain                                                                                 |Effort                      |
|-------------------------------|--------------|------------------------------------------------------------------------------------------------|----------------------------|
|1. Research phase              |Plan, Work    |Eliminates redundant file searching during plan/work. HumanLayer reports 40-60% context savings.|Medium                      |
|2. Context utilization         |All           |Prevents quality degradation in later phases of long sessions.                                  |High (workflow architecture)|
|3. Persistent research         |Plan, Compound|Eliminates re-investigation of the same codebase areas. Compounds across cycles.                |Medium                      |
|4. Research → Plan feed        |Plan          |Plans include verified paths and patterns vs. guesses. Fewer implementation-time corrections.   |Low                         |
|5. Phase compaction            |Work          |Prevents context exhaustion in multi-phase implementations.                                     |Medium                      |
|6. Auto vs. Manual verification|Plan, Work    |Makes human review gates explicit and efficient.                                                |Low                         |
|7. Human leverage hierarchy    |All           |Catches errors at highest leverage. One bad research line = thousands of bad code lines.        |Medium (process change)     |
|8. “Not Doing” section         |Plan          |Prevents scope creep. Two lines of template change.                                             |Trivial                     |
|9. Sub-agent specialization    |Plan          |Better structured research output, less noise in context.                                       |Medium                      |
|10. “End State” section        |Plan          |Grounds implementation in the goal, not just the steps.                                         |Trivial                     |

-----

## Refactor Plan for Junior Developer

### Overview

Add HumanLayer’s “Frequent Intentional Compaction” principles to the compound-engineering plugin. The refactor introduces a dedicated research phase, persistent research artifacts, research-grounded planning, phase-by-phase compaction during work, and explicit human-review gates. The goal: CE’s compounding loop becomes context-aware and produces better outcomes in brownfield codebases.

### Priority Order

Implement in this order. Each item is independently shippable and testable.

-----

### Phase 1: Plan Template Enhancements (Trivial — ship first)

**What to do**: Modify the `ce:plan` skill’s plan template to add three new sections.

**Files to change**: `plugins/compound-engineering/skills/ce:plan/SKILL.md` (or wherever the plan template lives).

**Specific additions to the plan markdown template**:

1. Add a `## Desired End State` section after “Overview” — describe the target state and how to verify it.
1. Add a `## What We're NOT Doing` section after “Desired End State” — explicitly list out-of-scope items.
1. Split every phase’s “Success Criteria” into two sub-sections: `#### Automated Verification` (commands the agent runs) and `#### Manual Verification` (things the human checks).

**Testing**: Generate a plan with `/ce:plan` for a real feature. Verify the three new sections appear and are filled with meaningful content, not boilerplate.

-----

### Phase 2: Research Command (`/ce:research`) (Medium — core new capability)

**What to do**: Create a new `/ce:research` command and supporting skill that produces a standalone research document.

**New files**:

- `plugins/compound-engineering/commands/ce:research.md` — slash command definition
- `plugins/compound-engineering/skills/ce:research/SKILL.md` — skill instructions
- `plugins/compound-engineering/agents/research/codebase-locator.md` — finds WHERE files/components live
- `plugins/compound-engineering/agents/research/codebase-analyzer.md` — documents HOW specific code works
- `plugins/compound-engineering/agents/research/codebase-pattern-finder.md` — finds examples of existing patterns

**Behavior**:

1. User invokes `/ce:research <topic or ticket>`.
1. Agent reads any mentioned files fully in the main context.
1. Agent decomposes the research question into parallel sub-agent tasks using the three specialized agents.
1. Sub-agents return structured findings with file:line references.
1. Main agent synthesizes findings into a research document.
1. Document is written to `docs/research/YYYY-MM-DD-description.md` with YAML frontmatter (date, git_commit, branch, topic, tags, status).
1. The research document documents what IS, not what SHOULD BE. No recommendations, no critiques, no improvements suggested.

**Key design rules for sub-agents** (copy from HumanLayer’s approach):

- `codebase-locator`: Only finds files and reports their paths. Does not analyze or evaluate.
- `codebase-analyzer`: Reads specific files and explains data flow, function signatures, dependencies. Does not suggest changes.
- `codebase-pattern-finder`: Finds existing examples of a pattern in the codebase. Does not propose new patterns.

**Research document template**:

```markdown
---
date: YYYY-MM-DDTHH:MM:SSZ
git_commit: <hash>
branch: <branch>
topic: "<research question>"
tags: [research, <component-names>]
status: complete
---

# Research: <Topic>

## Research Question
<original query>

## Summary
<high-level findings>

## Detailed Findings

### <Component/Area 1>
- Description of what exists (file.ext:line)
- How it connects to other components

### <Component/Area 2>
...

## Code References
- `path/to/file.py:123` — what's there
- `another/file.ts:45-67` — what the code block does

## Architecture Documentation
<current patterns, conventions, design implementations>

## Open Questions
<areas needing further investigation>
```

**Testing**: Run `/ce:research` on a non-trivial area of your own codebase. Verify the output contains real file:line references, not hallucinated paths. Verify sub-agents return structured, non-evaluative findings.

-----

### Phase 3: Wire Research Into Plan (Low effort — high value)

**What to do**: Modify `/ce:plan` to optionally accept a research document path. When provided, the plan command reads the research doc first and references it throughout the plan.

**Files to change**: `plugins/compound-engineering/skills/ce:plan/SKILL.md`

**Specific changes**:

1. Add parameter support: `/ce:plan docs/research/2026-03-26-auth-flow.md`.
1. When a research doc is provided, read it fully before spawning any sub-agents.
1. Add a `## Research Reference` section at the top of the plan that links back to the research doc.
1. In the “Current State Analysis” section, cross-reference research findings instead of re-investigating.
1. If no research doc is provided and the task is non-trivial, print a suggestion: “Consider running `/ce:research` first for better plan quality.”

**Testing**: Generate two plans for the same feature — one with research, one without. Compare the specificity of file references, test strategies, and phase design. The research-grounded plan should be measurably more precise.

-----

### Phase 4: Phase-by-Phase Compaction in Work (Medium effort)

**What to do**: Modify `/ce:work` to add compaction checkpoints between implementation phases.

**Files to change**: `plugins/compound-engineering/skills/ce:work/SKILL.md` (or equivalent)

**Specific changes**:

1. After completing each phase and verifying automated success criteria, update the plan file: check off completed items, add a brief status note with timestamp.
1. After updating the plan, pause for manual verification if the plan’s Manual Verification section has items for that phase.
1. For plans with 3+ phases, add a suggestion after each phase: “Context is filling up. Consider restarting with `/ce:work <plan-path>` — I’ll pick up from the first unchecked item.”
1. When resuming a plan with existing checkmarks, trust completed work and start from the first unchecked item.

**Testing**: Create a 4-phase plan. Run `/ce:work` through all 4 phases. Verify checkmarks appear in the plan file after each phase. Verify the agent can resume from phase 3 if the session is restarted.

-----

### Phase 5: Guided Mode (`/ce:guided`) (Medium effort — process change)

**What to do**: Create a human-gated workflow mode that pauses between research, plan, and work for human review.

**New files**:

- `plugins/compound-engineering/commands/ce:guided.md` — slash command

**Behavior**:

1. Run `/ce:research` and present findings. Wait for human approval.
1. Run `/ce:plan` with the approved research doc. Present the plan. Wait for human approval.
1. Run `/ce:work` with the approved plan. Pause between phases for manual verification.
1. Run `/ce:review` on the completed work.
1. Run `/ce:compound` to capture learnings.

**Key distinction from `/lfg`**: `/lfg` is autonomous. `/ce:guided` is the high-leverage, human-in-the-loop version for complex or brownfield tasks. The blog’s leverage hierarchy should be documented in the skill: reviewing research gives more leverage than reviewing plans, which gives more leverage than reviewing code.

**Testing**: Run `/ce:guided` on a real bug fix in a non-trivial codebase. Verify the human is prompted at each gate. Verify the final PR quality is measurably better than an equivalent `/lfg` run.

-----

### Phase 6: Research-Aware Compound (`/ce:compound` enhancement) (Low effort)

**What to do**: Modify `/ce:compound` to index and update research documents alongside solution docs.

**Files to change**: `plugins/compound-engineering/skills/compound-docs/SKILL.md`

**Specific changes**:

1. When compounding after a task that had a research doc, check if the research doc is still accurate. If the implementation changed things, update the research doc’s status to `outdated` or append a “Post-Implementation Update” section.
1. When the `learnings-researcher` agent runs during future plan steps, also search `docs/research/` for relevant prior research.
1. Add research docs to the `/ce:compound-refresh` cycle — stale research should be flagged for update or archival.

**Testing**: Complete a full research → plan → work → compound cycle. Verify the research doc is referenced in the compound output. Run `/ce:plan` on a related feature and verify the prior research surfaces.

-----

### Phase 7: Sub-Agent Specialization Refinement (Medium effort — optional)

**What to do**: Refactor the existing research agents to follow HumanLayer’s specialization model more closely.

**Files to change**: Agents in `plugins/compound-engineering/agents/research/`

**Key principle**: Each agent does one thing, returns structured output, and does not evaluate or recommend. The current `repo-research-analyst` tries to do too much in a single pass. Split it:

- `codebase-locator` → WHERE things are (paths only)
- `codebase-analyzer` → HOW things work (data flow, function signatures)
- `codebase-pattern-finder` → EXAMPLES of existing patterns (find-by-similarity)

The existing `learnings-researcher` stays as-is — it searches compound docs, which is a different concern.

**Testing**: Run the specialized agents individually against a codebase area. Compare the precision and compactness of their output to the current generic `repo-research-analyst`.

-----

## Decisions Log

These are the explicit decisions baked into this plan. If the implementer disagrees, raise it before starting.

1. **Research is optional, not mandatory.** The `/ce:plan` command still works without research. The suggestion to run research first is just that — a suggestion. Quick tasks don’t need it.
1. **Research documents live in `docs/research/`, not `thoughts/`.** CE already uses `docs/` as its artifact directory. HumanLayer’s `thoughts/` convention is specific to their tooling (humanlayer thoughts sync). We adapt the concept, not the directory name.
1. **No context utilization monitoring in v1.** Gap 2 (context awareness) requires deep integration with the agent runtime to measure token usage. This is deferred. Instead, we use compaction checkpoints as a proxy — the agent doesn’t measure context usage, but the workflow forces periodic compaction regardless.
1. **`/lfg` stays autonomous.** We don’t break existing behavior. `/ce:guided` is the new human-gated mode. Users choose based on task complexity.
1. **Sub-agents are “documentarians, not evaluators.”** This phrase from HumanLayer is now a core principle. Research agents describe. They do not recommend, critique, or propose improvements. This prevents research from biasing the plan toward premature solutions.
1. **YAML frontmatter on research docs is mandatory.** It enables future tooling (search, refresh, staleness detection). The fields are: date, git_commit, branch, topic, tags, status.
1. **Phase order is non-negotiable.** Ship Phase 1 first (trivial template changes, immediate value). Then Phase 2 (core new capability). Then Phase 3 (wiring). Phases 4-7 are independently shippable after that.

-----

## Confidence Assessment

**Confidence: 8/10 before saving.**

The two points of uncertainty:

- I could not read the actual SKILL.md source files for `ce:plan`, `ce:work`, `ce:review` due to GitHub access restrictions. The README and changelog provided enough signal to identify structural gaps, but some of what I’ve flagged as “missing” may already exist in a lighter form within the skill instructions.
- The “context utilization” gap (Gap 2) is real but may not be solvable at the plugin level — it may require Claude Code runtime integration.
