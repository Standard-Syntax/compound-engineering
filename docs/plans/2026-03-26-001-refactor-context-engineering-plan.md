---
title: refactor: Add context engineering primitives to compound-engineering plugin
type: refactor
status: completed
date: 2026-03-26
origin: docs/brainstorms/2026-03-26-context-engineering-refactor-requirements.md
---

# refactor: Add Context Engineering Primitives

## Tasks

- [ ] **Phase 1: `ce:research` skill** (COMPLETED)
  - [x] Create `skills/ce-research/SKILL.md`
  - [x] Create `skills/ce-research-beta/SKILL.md`
  - [x] Create `docs/research/` directory and README
- [x] **Phase 2: `ce:plan` modifications** (COMPLETED)
  - [x] Add research artifact check (Step 0.5) to `skills/ce-plan/SKILL.md`
  - [x] Add "What We're NOT Doing" section to all plan templates
  - [x] Separate automated/manual verification in plan templates
  - [x] Add quality cascade warning at top of plans
- [x] **Phase 3: LangGraph engine + `ce:work` modifications** (COMPLETED)
  - [x] Add phase tracking fields to `ce_engine/src/ce_engine/state.py`
  - [x] Add `phase_compact_node` to `ce_engine/src/ce_engine/nodes.py`
  - [x] Add `[PHASE_COMPLETE]` and `[COMPACT]` routing to `ce_engine/src/ce_engine/graph.py`
  - [x] Add context budget guidance to `ce_engine/src/ce_engine/prompts.py`
  - [x] Update `skills/ce-work/SKILL.md` to document new engine behavior
- [x] **Phase 4: `ce:compound` enhancements** (COMPLETED)
  - [x] Add research artifact linking to `skills/ce-compound/SKILL.md`
  - [x] Add Research Corrections field capture
  - [x] Add CLAUDE.md architectural pattern prompt
- [x] **Phase 5: `ce:compact` utility skill** (COMPLETED)
  - [x] Create `skills/ce-compact/SKILL.md`

## Overview

Add five context management primitives to the compound-engineering plugin, closing 7 gaps between the plugin's current workflows and HumanLayer's Frequent Intentional Compaction (FIC) methodology. The five phases are implemented in order; each phase is independently valuable but builds on the previous one.

**Quality cascade warning:** A mistake in the plan leads to 100s of bad lines of code. A mistake in the research leads to 1000s. Review this plan carefully before implementation.

## Problem Statement

LLMs are stateless functions. The only lever is the quality of what is in the context window. The plugin's workflows currently:

1. Run research inside the plan context window, polluting it before planning begins
2. Have no structured compaction protocol between phases
3. Provide no context utilization guidance
4. Lack explicit scope boundaries in plans
5. Conflate automated and manual verification
6. Discard research after each session (no persistent research repository)
7. Provide no quality cascade awareness in prompts

## Proposed Solution

Five incremental phases, each adding one context primitive:

| Phase | Primitive | Skill/Component Modified |
|-------|-----------|--------------------------|
| 1 | Standalone research phase → `ce:research` | New skill |
| 2 | Research-aware planning + scope boundaries | `ce:plan` |
| 3 | Phase-gated implementation + compaction | `ce_engine` (LangGraph) + `ce:work` |
| 4 | Research linking in compounding | `ce:compound` |
| 5 | General-purpose compaction utility | New skill |

## Technical Approach

### Phase 1: `ce:research` Skill

**New file:** `plugins/compound-engineering/skills/ce-research/SKILL.md`

Also create a beta version for safe rollout:
**New file:** `plugins/compound-engineering/skills/ce-research-beta/SKILL.md` (with `disable-model-invocation: true`)

#### Skill Design

```
skills/
  ce-research/
    SKILL.md        # Stable version
  ce-research-beta/
    SKILL.md        # Beta version for staged rollout
```

**What it does:**

1. Accept a research question (feature, bug, or architectural question)
2. Check `docs/research/` for existing relevant artifacts (reuse before re-research)
3. Spawn 4 parallel sub-agents:
   - `compound-engineering:research:repo-research-analyst` — codebase structure, patterns, file locations
   - `compound-engineering:research:best-practices-researcher` — external best practices
   - `compound-engineering:research:framework-docs-researcher` — framework docs via Context7
   - `compound-engineering:research:git-history-analyzer` — recent relevant changes
4. Assemble findings into `docs/research/YYYY-MM-DD-slug.md` with YAML frontmatter

**Output format:**

```yaml
---
date: 2026-03-26T10:00:00-05:00
topic: "Auth architecture research"
tags: [research, auth, security]
status: complete
git_commit: abc1234
branch: main
---

# Auth Architecture Research

## Research Question
[What are we investigating and why]

## Summary
[2-3 sentence executive summary]

## Detailed Findings

### Codebase Structure
[File:line references]

### Architecture Patterns
[How existing code handles this]

### External Best Practices
[Links and key points]

### Recent Changes
[git log findings relevant to this topic]

## Architecture Documentation
[Key architectural decisions observed, documented as-is]

## Code References
- `app/services/auth_service.rb:42` — [1-line summary]
- `app/models/user.rb:10` — [1-line summary]
```

**Key instructions to the orchestrating agent:**
- Document what IS, not what SHOULD BE (pure description, no recommendations)
- Include `file:line` references for every codebase claim
- End with developer prompt: "Please review this research before proceeding to planning. A misunderstanding here cascades into the plan and implementation."

**Invocation:**
```
/ce:research [feature description or question]
```

#### Beta Version

The beta version (`ce-research-beta`) ships alongside the stable version during the rollout period. Per the beta skills framework (`docs/solutions/skill-design/beta-skills-framework.md`), beta skills use `-beta` suffix and `disable-model-invocation: true` to prevent auto-triggering.

After the beta period (and once the stable version is verified), the stable version becomes the default and the beta version is archived.

---

### Phase 2: `ce:plan` Modifications

**Modify:** `plugins/compound-engineering/skills/ce-plan/SKILL.md`

#### Change 1: Accept Optional Research Input

After Step 0 (requirements check), add Step 0.5:

```
### 0.5. Research Artifact Check

If the user provides a path to a research artifact (e.g., `docs/research/2026-03-26-auth-research.md`), read it and skip inline research.

If no research artifact is provided:
1. Search `docs/research/` for relevant existing artifacts:
   ```bash
   ls docs/research/*.md 2>/dev/null | head -10
   ```
2. If relevant artifacts exist, announce: "Found existing research: [path]. Use it as input?"
3. If none exist, warn: "No research artifact provided. Planning without research is lower quality — inline research will proceed but results will be less comprehensive."
```

#### Change 2: Add "What We're NOT Doing" Section

In all three plan templates (MINIMAL, MORE, A LOT), add a required `## What We're NOT Doing` section before `## Sources & References`.

**Required location:** After `## Scope Boundaries` (or equivalent) and before any reference sections.

```markdown
## What We're NOT Doing
- [Explicitly list out-of-scope items]
- [Adjacent concerns deferred to future work]
- [Known limitations of this approach]
```

#### Change 3: Separate Verification Criteria

In the MORE and A LOT templates, under `### Success Criteria` (or `## Acceptance Criteria` in A LOT), replace the single checklist with two sub-sections:

```markdown
### Success Criteria

#### Automated Verification
- [ ] Tests pass: `make test`
- [ ] Linting: `make lint`
- [ ] Type check: `npm run typecheck`

#### Manual Verification
- [ ] Feature works in UI
- [ ] Edge case X handled correctly
- [ ] No regressions in related features
```

#### Change 4: Quality Cascade Warning

At the very top of the plan output (after the YAML frontmatter, before the title), add:

```
> **⚠️ Review this plan carefully before implementation.**
> A mistake in the plan leads to 100s of bad lines of code.
> A mistake in the research leads to 1000s.
```

---

### Phase 3: `ce:work` — LangGraph Engine + Skill Wrapper

**Modify (engine first):** `ce_engine/src/ce_engine/graph.py`, `ce_engine/src/ce_engine/state.py`, `ce_engine/src/ce_engine/nodes.py`
**Modify (wrapper second):** `plugins/compound-engineering/skills/ce-work/SKILL.md`

#### LangGraph Engine Changes

**Architecture decision:** Engine changes first, skill wrapper second. See origin doc for rationale.

**Key primitives to add:**

##### 1. Phase Tracking in State

In `state.py`, add to `WorkState`:

```python
# Phase tracking
current_phase: int = 0
phase_definitions: list[str] = Field(default_factory=list)
manual_verification_pending: bool = False
files_read_count: int = 0  # Track direct file reads for compaction trigger
```

##### 2. Phase Complete Routing

In `graph.py`, modify `_route_intent()` to recognize a new LLM output marker:

The LLM is instructed to output `[PHASE_COMPLETE]` at the end of each planned phase. The routing function detects this and routes to a new `phase_compact_node`.

```python
def _route_intent(state: WorkState) -> str:
    intent = state.work_intent.intent
    if "[PHASE_COMPLETE]" in intent:
        return "phase_compact"
    # ... existing routing logic unchanged ...
```

##### 3. New Node: `phase_compact_node`

In `nodes.py`, add `phase_compact_node`:

```python
async def phase_compact_node(state: WorkState) -> dict:
    """
    Called when LLM outputs [PHASE_COMPLETE].
    1. Increment phase counter
    2. Check if plan has manual_verification items for this phase
    3. If yes: set manual_verification_pending=True, interrupt for human
    4. If no: continue to next iteration
    5. Check files_read_count; if > 15, write progress compaction before continuing
    """
    next_phase = state.current_phase + 1
    plan = _read_plan(state.plan_ref)
    phase_items = _get_manual_verification_items(plan, next_phase)

    updates: dict = {"current_phase": next_phase}

    if phase_items:
        updates["manual_verification_pending"] = True
        updates["pending_verification_items"] = phase_items
        return updates

    # No manual verification; continue
    updates["manual_verification_pending"] = False
    return updates
```

##### 4. Manual Verification Interrupt

The existing `human_interrupt_node` already handles pausing. The `phase_compact_node` sets `manual_verification_pending=True`, which the existing routing logic already knows how to handle via the interrupt mechanism.

**New interrupt format** (modify `human_interrupt_node` prompt to detect phase context):

```
Phase [N] Complete — Ready for Manual Verification

Automated checks passed:
- [x] Tests pass
- [x] Linting clean

Please verify manually:
- [ ] Feature works in UI
- [ ] Edge case handled

Reply when ready to proceed to Phase [N+1].
```

##### 5. Compaction Trigger

After each `llm_work_node` iteration, increment `files_read_count` based on how many files were read. Add to the LLM prompt: "If you have read more than 15 files directly in this session, include `[COMPACT]` in your intent output." The routing function handles this:

```python
if "[COMPACT]" in intent:
    return "compact_progress"
```

A new `compact_progress_node` writes a structured summary to the plan file (check off completed items, note blockers, key decisions) before the next iteration.

##### 6. Context Budget Guidance in LLM Prompt

In `prompts.py`, add to the work system prompt:

```
- Prefer sub-agents for file reading, test running, and log inspection
- Keep context focused on the current phase; do not pre-load files for future phases
- If you have read more than 15 files directly in this session, output [COMPACT] to trigger compaction
- Keep context utilization in the 40-60% range
```

#### Skill Wrapper Changes

After engine changes land, update `ce-work/SKILL.md` to:

1. Document the new engine behavior (phase tracking, verification gates, compaction)
2. Update the session resume instructions to account for phase state
3. Add guidance on reading the plan file for phase definitions (so the agent knows what counts as a "phase")

---

### Phase 4: `ce:compound` Enhancements

**Modify:** `plugins/compound-engineering/skills/ce-compound/SKILL.md`

#### Change 1: Link Research to Solutions

In **Phase 0.5 (Auto Memory Scan)**, also check for a research artifact in `docs/research/` that matches the problem being documented:

```python
# After auto memory check
research_matches = _find_relevant_research(problem_description)
if research_matches:
    research_context = f"\n\n## Relevant Research Artifact\n{research_matches[0]['path']}\n"
```

If a research artifact is found, add a `research_artifacts` section to the solution frontmatter:

```yaml
research_artifacts:
  - docs/research/2026-03-26-auth-architecture-research.md
```

And cross-reference in the solution body:

```markdown
## Related Research
This solution was informed by [docs/research/2026-03-26-auth-architecture-research.md](path).
```

#### Change 2: Capture Research Corrections

In **Phase 1 (Parallel Research)** → Solution Extractor, add a new output field:

```
#### Research Corrections
[Misconceptions or incorrect assumptions from the research artifact that were corrected during implementation, and why]
```

These get written to the solution doc under a `## Research Corrections` section, preventing future research from making the same mistakes.

#### Change 3: CLAUDE.md Architectural Pattern Prompt

After Phase 2 (Assembly & Write), add:

```
If the implementation revealed architectural patterns, data flows, or integration points not documented in CLAUDE.md, prompt the developer:
"Implementation revealed a pattern not documented in CLAUDE.md: [brief description]. Would you like to add it?"
```

---

### Phase 5: `ce:compact` Utility Skill

**New file:** `plugins/compound-engineering/skills/ce-compact/SKILL.md`

#### Skill Design

```
skills/
  ce-compact/
    SKILL.md        # General-purpose compaction utility
```

**Invocation:**
```
/ce:compact [optional: output path]
```

**What it does:**

1. Reads the current plan file (if one exists)
2. Reads recent conversation context to identify completed steps
3. Writes a structured compaction summary

**Output format:**

```markdown
## Compaction Summary
### Goal
[What we're trying to accomplish]
### Approach
[Strategy being used]
### Completed Steps
- [Step with outcome]
### Current Status
[Where we are now, including any failures]
### Relevant Files
- `path/to/file.ext` - [1-line summary of role]
### Key Decisions
- [Decision and rationale]
### Next Steps
- [What remains]
```

**Output location:** `.context/compound-engineering/compact-YYYYMMDD-HHMMSS.md` (ephemeral) or user-specified path.

**Key instruction:** "This compaction must be sufficient to resume work in a new context window with no additional background."

---

## Implementation Phases

### Phase 1: `ce:research` Skill

**Effort:** Medium

| Task | File | Action |
|------|------|--------|
| Create `ce:research` skill | `skills/ce-research/SKILL.md` | New file |
| Create `ce-research-beta` skill | `skills/ce-research-beta/SKILL.md` | New file (beta) |
| Create `docs/research/` directory | `docs/research/` | New directory |
| Add README or index to `docs/research/` | `docs/research/README.md` | New file (optional index) |

**Rollout:** Beta skill ships alongside stable. After verification, stable becomes default.

### Phase 2: `ce:plan` Modifications

**Effort:** Medium

| Task | File | Action |
|------|------|--------|
| Add research artifact check (Step 0.5) | `skills/ce-plan/SKILL.md` | Modify |
| Add "What We're NOT Doing" to all templates | `skills/ce-plan/SKILL.md` | Modify |
| Separate automated/manual verification | `skills/ce-plan/SKILL.md` | Modify |
| Add quality cascade warning | `skills/ce-plan/SKILL.md` | Modify |

**Rollout:** Direct modification. No beta needed — non-breaking additive changes.

### Phase 3: LangGraph Engine + `ce:work` Wrapper

**Effort:** Medium-High (engine changes are the bulk)

| Task | File | Action |
|------|------|--------|
| Add phase fields to `WorkState` | `ce_engine/src/ce_engine/state.py` | Modify |
| Add `phase_compact_node` | `ce_engine/src/ce_engine/nodes.py` | Modify |
| Add `compact_progress_node` | `ce_engine/src/ce_engine/nodes.py` | Modify |
| Add `[PHASE_COMPLETE]` and `[COMPACT]` routing | `ce_engine/src/ce_engine/graph.py` | Modify |
| Add context budget guidance to prompt | `ce_engine/src/ce_engine/prompts.py` | Modify |
| Update manual verification interrupt format | `ce_engine/src/ce_engine/nodes.py` | Modify |
| Update `ce-work` skill wrapper | `plugins/compound-engineering/skills/ce-work/SKILL.md` | Modify |

**Rollout:** Engine changes first (PR 1), then skill wrapper (PR 2).

### Phase 4: `ce:compound` Enhancements

**Effort:** Small

| Task | File | Action |
|------|------|--------|
| Add research artifact linking in Phase 0.5 | `skills/ce-compound/SKILL.md` | Modify |
| Add Research Corrections field to Phase 1 | `skills/ce-compound/SKILL.md` | Modify |
| Add CLAUDE.md pattern prompt after Phase 2 | `skills/ce-compound/SKILL.md` | Modify |

### Phase 5: `ce:compact` Skill

**Effort:** Small

| Task | File | Action |
|------|------|--------|
| Create `ce:compact` skill | `skills/ce-compact/SKILL.md` | New file |

---

## Alternative Approaches Considered

### Inline Research Inside Planning (Rejected)

**Approach:** Keep research inside `ce:plan` but with better compaction.

**Why rejected:** The context pollution problem is structural, not fixable with better prompts. Research sub-agents return their full output into the parent context. The fix requires a separate phase with a disk-written artifact — not better prompt engineering within the same context window.

### Verification Gates in Skill Wrapper Only (Rejected for Phase 3)

**Approach:** Add verification gates only to the `ce-work` SKILL.md, not the LangGraph engine.

**Why rejected:** The skill wrapper does not own session state. If the user resumes a `ce-work` session, the wrapper has no way to know which phase was completed. The engine is the right place for phase state.

### One Big PR (Rejected)

**Approach:** All 5 phases in one PR.

**Why rejected:** The beta skills framework exists for good reason — workflow changes that affect all downstream steps should be rolled out incrementally. Phase 1 enables everything else; shipping it first lets each phase be verified independently.

---

## System-Wide Impact

### Interaction Graph

- `ce:research` → produces artifact → `ce:plan` consumes artifact
- `ce:plan` → produces plan with phase markers → `ce:work` executes per phase
- `ce:work` → writes progress to plan file → plan file becomes compaction artifact
- `ce:compound` → reads research artifact → produces solution with cross-reference

### Error & Failure Propagation

- If `ce:research` produces poor quality artifact → `ce:plan` makes poor plan → `ce:work` implements wrong thing. Mitigated by: required developer review of research before planning.
- If engine compaction fails → session continues but context fills → quality degrades. Mitigated by: 15-file trigger is conservative.
- If plan has no phase markers → `[PHASE_COMPLETE]` never output → no verification gates fire. Mitigated by: planning template requires phases.

### State Lifecycle Risks

- Research artifacts persist indefinitely → may become stale. Mitigated by: `status: stale` frontmatter field + `ce:compound` captures corrections.
- Phase state in LangGraph session → resume works correctly. No partial failure risk since each iteration is atomic.

### API Surface Parity

- `ce:plan` gains new arguments (research path). No breaking change to existing behavior (optional parameter).
- `ce:work` gains new output format (phase pause). No breaking change — human_interrupt was already used.
- `ce:compound` adds research linking. No breaking change — existing behavior unchanged when no research artifact found.

---

## Acceptance Criteria

### Phase 1 (ce:research)
- [ ] Research artifact written to `docs/research/YYYY-MM-DD-slug.md` with valid YAML frontmatter
- [ ] Artifact includes `file:line` references for all codebase claims
- [ ] Artifact ends with developer review prompt
- [ ] `ce:research` can be invoked with a feature description and produces an artifact within 5 minutes
- [ ] Beta version ships alongside stable version

### Phase 2 (ce:plan modifications)
- [ ] Plan templates include `## What We're NOT Doing` section
- [ ] Plan templates separate `#### Automated Verification` and `#### Manual Verification`
- [ ] `ce:plan` accepts a research artifact path and skips inline research
- [ ] `ce:plan` searches `docs/research/` for existing artifacts before spawning new research
- [ ] Quality cascade warning appears at top of every plan

### Phase 3 (ce:work / LangGraph engine)
- [ ] Engine tracks current phase number in state
- [ ] LLM outputting `[PHASE_COMPLETE]` triggers phase compact node
- [ ] Phase compact node checks for manual verification items
- [ ] If manual items exist, engine pauses with structured pause format
- [ ] Agent resumes correctly from human interrupt
- [ ] `[COMPACT]` output triggers progress compaction to plan file
- [ ] 15-file direct read triggers compaction guidance in LLM output
- [ ] Context budget guidance appears in work system prompt

### Phase 4 (ce:compound enhancements)
- [ ] Solution docs reference associated research artifacts when one exists
- [ ] Research corrections are captured as a section in solution docs
- [ ] Developer is prompted to update CLAUDE.md for architectural patterns after implementation

### Phase 5 (ce:compact)
- [ ] `ce:compact` produces structured summary sufficient to resume in new context
- [ ] Output written to `.context/compound-engineering/compact-TIMESTAMP.md` by default
- [ ] Custom output path accepted as argument

---

## Success Metrics

- Research artifacts in `docs/research/` are discoverable and reusable across sessions
- Plans produced after consuming a research artifact are measurably more accurate than plans without research (based on: fewer plan gaps, fewer post-implementation scope changes)
- Work sessions maintain context utilization in the 40-60% range during multi-phase implementations
- Solution docs reference their source research artifacts — traceable from problem to solution to research
- Compaction artifacts are sufficient to resume work in a new context window with no additional background

---

## Dependencies & Risks

| Dependency | Risk | Mitigation |
|-----------|------|------------|
| `git-history-analyzer` agent exists and is functional | Agent not found → Phase 1 degraded | Use existing agents as fallback; do not block on new agent |
| LangGraph engine state changes are backward-compatible | Resume from old sessions breaks | New fields have defaults; existing sessions resume correctly |
| `docs/research/` directory created before Phase 2 | ce:plan search fails silently | Create directory in Phase 1 |
| Beta rollout period for ce:research | Dual-maintenance burden | Short beta period (1-2 weeks); promote quickly |

---

## Resource Requirements

- **New skills:** 3 (`ce:research`, `ce-research-beta`, `ce:compact`)
- **Modified skills:** 3 (`ce:plan`, `ce:work`, `ce:compound`)
- **Modified engine files:** 4 (`state.py`, `nodes.py`, `graph.py`, `prompts.py`)
- **New directories:** 1 (`docs/research/`)
- **Testing:** Manual testing of each phase; no automated tests for skill prompts

---

## Future Considerations

- **Research artifact search:** Build a lightweight index or grep-based search for `docs/research/` so future `ce:plan` can find relevant artifacts without enumerating all files
- **Automated compaction trigger:** Instead of counting file reads, instrument the context pack size and trigger compaction when it exceeds a threshold (e.g., 60% of context window)
- **Verification gate automation:** Some manual verification items could be automated with better prompting; future work could detect which manual items have automation potential

---

## Sources & References

### Origin
- **Requirements doc:** [docs/brainstorms/2026-03-26-context-engineering-refactor-requirements.md](docs/brainstorms/2026-03-26-context-engineering-refactor-requirements.md)
  - Key decisions: 5-phase rollout order, LangGraph engine first/then skill wrapper, 15-file compaction threshold, `docs/research/` naming convention

### Internal References
- LangGraph engine: `ce_engine/src/ce_engine/graph.py`, `ce_engine/src/ce_engine/nodes.py`, `ce_engine/src/ce_engine/state.py`, `ce_engine/src/ce_engine/prompts.py`
- ce-work skill: `plugins/compound-engineering/skills/ce-work/SKILL.md`
- ce-plan skill: `plugins/compound-engineering/skills/ce-plan/SKILL.md`
- ce-compound skill: `plugins/compound-engineering/skills/ce-compound/SKILL.md`
- Research agents: `plugins/compound-engineering/agents/research/`
- Beta skills framework: `docs/solutions/skill-design/beta-skills-framework.md`
- Script-first architecture (compaction pattern): `docs/solutions/skill-design/script-first-skill-architecture.md`

### External References
- HumanLayer Advanced Context Engineering: https://www.humanlayer.dev/blog/advanced-context-engineering
- HumanLayer research_codebase.md pattern (research phase separation)
