---
title: "Improve the Compound Engineering Feedback Loop"
type: feat
status: completed
date: 2026-03-26
---

# Improve the Compound Engineering Feedback Loop

## Overview

Unify the knowledge pipeline between `ce:compound` and the ce_engine, add plan-gap feedback, retroanalysis, persistent checkpointing, and an enriched context pack. The compounding loop is currently severed: compound docs accumulate in `docs/solutions/` but the work engine never reads them.

## Problem Statement

Two disconnected knowledge stores exist:

1. `docs/solutions/` — where `ce:compound` writes categorized solution docs
2. `.context/compound-engineering/learnings/` — where the ce_engine's `prefetch_node` reads (only 2 most recent files, 500 chars each)

The work engine never reads compound docs. The compound step never writes to the work engine's local context directory. The loop is severed.

## Technical Approach

### Implementation Order

1. **Gap 1: Unify the Knowledge Pipeline** — everything else depends on this
2. **Gap 6: Persistent Checkpointing** — low risk, independently testable
3. **Gap 8: Enrich the Context Pack** — builds on Gap 1
4. **Gap 5: Plan Gap → Compound Feedback** — builds on Gap 1 and Gap 8
5. **Gap 7: Retroanalysis Phase** — builds on Gap 4

---

## Gap 1: Unify the Knowledge Pipeline

**Goal**: `prefetch_node` reads compound docs from `docs/solutions/` using relevance matching, not recency.

### Approach: Option A + C Hybrid

Replace the `_read_learnings()` "2 most recent files" approach with a **semantic frontmatter search** inspired by how `learnings-researcher` works, but as a direct node implementation rather than a separate agent.

**New `_read_learnings()` logic** (nodes.py:126-135 replacement):

1. Glob `docs/solutions/**/*.md` — all compound docs
2. Read **frontmatter only** (first 50 lines) of each candidate (avoids reading full content of irrelevant files)
3. Score each doc by:
   - `module` field match against task description keywords (weight: 3)
   - `component` field match (weight: 2)
   - `problem_type` field match (weight: 1)
   - `tags` field match (weight: 2)
   - `date` recency bonus: +1 for docs <30 days old (weight: 1)
4. Sort by total score descending, take top 5
5. For those 5, read full content (up to 1000 chars each)
6. If fewer than 5 candidates score above 0, fall back to 2 most recent for backward compatibility

**Backward compat**: `learnings_path` still works — `_read_learnings()` first searches `docs/solutions/`, then if that yields fewer than 2 docs, supplements from `learnings_path`.

**Config changes** (config.py):
- `solutions_path: Path = Path("docs/solutions")` — add `CE_SOLUTIONS_PATH` override
- `learnings_path` stays, used as fallback only

**Acceptance criteria:**
- [ ] `prefetch_node` includes compound docs relevant to current task (matched by module/component/tags/problem_type)
- [ ] Relevance matching beats "2 most recent" — considers task description and plan content
- [ ] `docs/solutions/` YAML frontmatter schema unchanged
- [ ] `retrospect` skill (plugins/compound-engineering/skills/retrospect/SKILL.md) can also read the unified store
- [ ] Config remains overridable via `CE_*` env vars

### Files to Change

| File | Change |
|------|--------|
| `ce_engine/src/ce_engine/config.py` | Add `solutions_path` setting |
| `ce_engine/src/ce_engine/nodes.py` | Replace `_read_learnings()` with frontmatter-scored search |

---

## Gap 6: Persistent Session Checkpointing

**Goal**: Replace `MemorySaver` with `SqliteSaver` so sessions survive process restarts.

### Approach

Use `langgraph.checkpoint.sqlite.SqliteSaver` as a drop-in replacement for `MemorySaver`.

**Changes to `graph.py`**:

```python
# graph.py lines 71-100
from langgraph.checkpoint.sqlite import SqliteSaver

def build_work_graph() -> CompiledGraph:
    # ... existing node/edge building ...
    checkpointer = SqliteSaver.from_conn_string(str(settings.checkpoint_db_path))
    return graph.compile(checkpointer=checkpointer)
```

**Changes to `config.py`**:
```python
checkpoint_db_path: Path = Path(".context/compound-engineering/checkpoints.db")
```

**Checkpoint cleanup** (new function in `graph.py` or new `cleanup.py`):
- On graph build, run cleanup if last cleanup was >24h ago
- Delete checkpoint records where `checkpoint_ts < now() - 7 days`
- Use a simple timestamp stored in a companion file: `.context/compound-engineering/.checkpoint_cleanup`

**Note**: The existing `MemorySaver` comment at graph.py:96-98 documents this limitation — update that comment when implementing.

**Acceptance criteria:**
- [ ] Work session interrupted by process exit can resume with same session ID
- [ ] Phase progress, error baselines, and human decisions survive restart
- [ ] Checkpoint DB path is configurable via `CE_CHECKPOINT_DB_PATH`
- [ ] Old checkpoints cleaned up automatically (7 day retention)

### Files to Change

| File | Change |
|------|--------|
| `ce_engine/src/ce_engine/config.py` | Add `checkpoint_db_path` setting |
| `ce_engine/src/ce_engine/graph.py` | Replace `MemorySaver` with `SqliteSaver`, add cleanup logic |

---

## Gap 8: Enrich the Context Pack

**Goal**: `prefetch_node` context pack includes compound knowledge and plan metadata, not just linting state.

### Approach

Extend `prefetch_node` to also read the plan file and extract structured data from it.

**New context pack sections** (in addition to existing `<project>`, `<current_task>`, `<pre_fetched>`, `<relevant_learnings>`):

**`<plan_metadata>`** — extracted from the plan file at `state.plan_ref`:
- `deferred_questions`: Lines in the plan tagged with `deferred:`, `unknown:`, `tbd:`, or `?`
- `scope_boundaries`: Sections titled "Out of Scope", "Not Doing", "Excludes"
- `phase_definitions`: All `## Phase N:` headings with their verification criteria
- `verification_criteria`: Checkbox items marked `[ ]` in the plan

**`<relevant_solutions>`** — from Gap 1 search:
- Up to 3 compound doc summaries, each: `title`, `module`, `root_cause`, `solution` (≤100 words total per summary)
- Format: `## [title] (module: X)\n**Root cause**: ...\n**Solution**: ...`

**`<research_artifact>`**:
- If `docs/research/` contains a file matching the plan's topic/tags, include: `path: docs/research/<filename>.md`

**Token budget**: Total context pack ≤4000 tokens. Sections have these limits:
- `<project>` + `<current_task>` + `<pre_fetched>`: ~1200 tokens (fixed)
- `<relevant_learnings>`: ~500 tokens (2 most recent fallback) or ~1500 tokens (Gap 1 search results)
- `<plan_metadata>`: ≤500 tokens (prioritize: deferred questions first, then scope boundaries, then phase definitions)
- `<relevant_solutions>`: ≤300 tokens (3 summaries × ≤100 words each)
- `<research_artifact>`: ≤100 tokens (just the path reference)

**Enforcement**: After assembling all sections, if total >4000 tokens, truncate `<relevant_learnings>` first (keep top 2 entries), then `<relevant_solutions>` (keep top 2), then `<plan_metadata>` (drop phase definitions). Never truncate `<project>` or `<current_task>`.

**Files to Change**:
| File | Change |
|------|--------|
| `ce_engine/src/ce_engine/nodes.py` | Add plan metadata extraction to `prefetch_node` |
| `ce_engine/src/ce_engine/state.py` | Add `relevant_solutions: list[SolutionSummary]` field to `WorkState` if needed |
| `ce_engine/src/ce_engine/prompts.py` | Add `<plan_metadata>`, `<relevant_solutions>`, `<research_artifact>` sections to template |

### New Model (state.py)

```python
class SolutionSummary(BaseModel, frozen=True):
    """Summary of a relevant compound doc for context pack."""
    title: str
    module: str
    root_cause: str
    solution: str  # ≤100 words
    file_path: str
    relevance_tags: list[str]
```

---

## Gap 5: Plan Gap → Compound Feedback

**Goal**: Plan gaps discovered during work feed into `ce:compound` and future `ce:plan` sessions.

### Approach

**1. Extend `ce:compound` Phase 0.5b** (SKILL.md):

Add a check for `.context/compound-engineering/plan-gaps.md` alongside the research artifact scan:

```
Phase 0.5b: Research Artifact + Plan Gaps Check
- If .context/compound-engineering/plan-gaps.md exists:
  - Read and parse gap entries
  - Tag each with: resolved / deferred
  - Pass to Phase 1 subagents tagged "(plan gaps)"
```

**2. Extend Solution Extractor subagent** to receive plan gap context:

The Solution Extractor (from ce:compound Phase 1) should:
- Receive plan gap entries as additional context
- Note which gaps were **resolved** during this work cycle (marked "include in this work")
- Note which gaps were **deferred** to next plan
- For resolved gaps: explain in the compound doc what the plan missed
- For deferred gaps: flag in compound doc for future planning

**3. Compound doc new section** (Phase 2 assembly):

```markdown
## Plan Gaps Encountered

### Resolved This Cycle
- **[Gap N]**: {description} — resolved by {what changed}

### Deferred to Next Plan
- **[Gap N]**: {description} — reason for deferral
```

**4. Extend `ce:plan` skill** to search compound docs tagged with plan-gap metadata:

In the plan template (plugins/compound-engineering/skills/ce-plan/SKILL.md), add a pre-search step:
- Before planning, grep `docs/solutions/` for docs with `tags: [plan-gap]` or `plan_gaps_encountered:` frontmatter
- Surface findings as: "Prior plans for [feature] missed [pattern] — see [doc]"

**5. Plan gap file persistence**: The `plan-gaps.md` file is **never deleted** after compound. It persists in `.context/compound-engineering/` for retroanalysis.

### Files to Change

| File | Change |
|------|--------|
| `plugins/compound-engineering/skills/ce-compound/SKILL.md` | Extend Phase 0.5b, Solution Extractor, add "Plan Gaps Encountered" section |
| `plugins/compound-engineering/skills/ce-plan/SKILL.md` | Add plan-gap search pre-step |

---

## Gap 7: Retroanalysis Phase

**Goal**: After documenting the solution, analyze whether the process itself can improve.

### Approach

Retroanalysis is **sub-step 2.5 within Phase 2 assembly** (runs before the write, not after it).

**Phase 2.5: Retroanalysis + Assembly** (replaces Phase 2.5 Selective Refresh Check)

1. Generate retroanalysis content:
   - Read the plan file at `state.plan_ref`
   - Read `.context/compound-engineering/plan-gaps.md` if it exists
   - Read the last review output from `.context/compound-engineering/`
   - Assess:
     - Did the plan predict the files that actually changed? (compare plan scope against git diff)
     - Were plan gaps avoidable with better research upfront?
     - Did review catch issues that should have been in the plan?
     - What would have made this cycle faster?
2. Assemble the complete compound doc including the retroanalysis section (see format below)
3. Validate YAML frontmatter
4. Write the file
5. If suggestions are actionable, ask: "Should I add this to CLAUDE.md or AGENTS.md?"

**Retroanalysis section format** (embedded in compound doc, not a separate file):

```markdown
## Retroanalysis

### Plan Accuracy
- Predicted correctly: {files that were actually changed}
- Unexpected changes: {files changed that weren't in plan scope}

### Process Assessment
- Avoidable gaps: {gaps that better research would have prevented}
- Plan → review gap: {issues caught by review that planning should have caught}
- Cycle speed: {what slowed the cycle down}

### Process Improvement Suggestions
- {Actionable suggestion 1}
- {Actionable suggestion 2}
```

**Compact-safe mode**: Retroanalysis is skipped. The lightweight assessment is folded into the compact doc's prevention section instead.

**Note**: ce:plan already searches `docs/solutions/` via learnings-researcher (Step 1, parallel task). Gap 5 adds a **plan-gap specific** pre-search step: before planning, also grep `docs/solutions/` for docs tagged `plan_gaps_encountered: true` in frontmatter, surfacing "prior plans for X missed Y" patterns.

**Files to Change**:

| File | Change |
|------|--------|
| `plugins/compound-engineering/skills/ce-compound/SKILL.md` | Rename Phase 2.5 to "Retroanalysis + Assembly"; retroanalysis runs as sub-step before file write |
| `plugins/compound-engineering/skills/retrospect/SKILL.md` | (Read-only reference — do not change) |

---

## System-Wide Impact

### Interaction Graph

- `prefetch_node` → now reads `docs/solutions/` (was reading only `.context/compound-engineering/learnings/`)
- `prefetch_node` → now reads plan file referenced in `state.plan_ref` (was not reading plan at all)
- `ce:compound` → now reads `.context/compound-engineering/plan-gaps.md` (was not reading it)
- `ce:compound` → now writes retroanalysis section (was not writing it)
- `ce:plan` → already searches `docs/solutions/` via learnings-researcher; Gap 5 adds plan-gap-specific pre-search (grep for `plan_gaps_encountered: true` in frontmatter)
- `build_work_graph()` → now uses `SqliteSaver` (was using `MemorySaver`)
- `validate_node`, `plan_gap_node` → no changes, but benefit from richer context pack

### Error & Failure Propagation

- If `docs/solutions/` is empty or missing: fall back to `learnings_path` (backward compat)
- If plan file doesn't exist: skip `<plan_metadata>` section silently (graceful degradation)
- If `checkpoint_db_path` parent dir doesn't exist: create it on graph build
- If SqliteSaver fails to connect or raises `sqlite3.DatabaseError` (corrupted DB): raise a clear error with guidance to delete the DB file and restart. Do not silently fall back to MemorySaver — that would break resume guarantees.
- If DB file is locked by another process: `SqliteSaver.from_conn_string()` raises `sqlite3.OperationalError` — catch and surface to user with "session may be in use by another process" message

### State Lifecycle Risks

- `plan-gaps.md` accumulates across sessions — no cleanup needed (persistence is intentional for retroanalysis)
- `checkpoints.db` grows with session history — 7-day cleanup mitigates this
- `context-pack.md` is overwritten each iteration — normal, no cleanup needed

### API Surface Parity

- CLI `--session-id` flag behavior unchanged — works the same with SqliteSaver
- `interrupt()` mechanism unchanged — still works for human-in-the-loop
- Graph routing unchanged

---

## Dependencies & Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `SqliteSaver` has different serialization format than `MemorySaver` | Low | High | Test resume with a mock session before deploying |
| Grep-based frontmatter search is slow on large `docs/solutions/` | Medium | Low | Frontmatter-only read (50 lines) before full read of top 5 |
| Compound doc YAML frontmatter is inconsistent across docs | Medium | Medium | Frontmatter validation in Phase 2 assembly catches this |
| Plan file format varies wildly between plans | Medium | Low | Skip `<plan_metadata>` if parsing fails, graceful degradation |
| Adding Phase 2.7 increases ce:compound runtime | Low | Low | Compact-safe mode skips it |

---

## Acceptance Criteria Summary

| Gap | Criterion |
|-----|-----------|
| Gap 1 | `prefetch_node` includes compound docs relevant to current task (matched by module/component/tags/problem_type) |
| Gap 1 | Relevance matching beats "2 most recent" — considers task description |
| Gap 1 | `docs/solutions/` YAML frontmatter schema unchanged |
| Gap 1 | `retrospect` skill can read from unified store |
| Gap 1 | Config overridable via `CE_*` env vars |
| Gap 6 | Session interrupted by process exit can resume with same session ID |
| Gap 6 | Phase progress, error baselines, human decisions survive restart |
| Gap 6 | Checkpoint DB path is configurable |
| Gap 6 | Old checkpoints cleaned up automatically (7 day retention) |
| Gap 8 | Context pack includes plan deferred questions and scope boundaries |
| Gap 8 | Context pack includes relevant compound doc summaries (≤3, ≤100 words each) |
| Gap 8 | Context pack includes research artifact reference when available |
| Gap 8 | Total context pack size stays ≤4000 tokens |
| Gap 5 | Plan gaps from work sessions appear in compound doc |
| Gap 5 | Future plans for similar features surface prior plan gap data |
| Gap 5 | Plan gap file persists after compound |
| Gap 7 | Compound docs include retroanalysis section when plan/review artifacts exist |
| Gap 7 | Retroanalysis findings tagged for discoverability |
| Gap 7 | Phase is skippable in compact-safe mode |

---

## Sources & References

### Internal References

- `prefetch_node`: `ce_engine/src/ce_engine/nodes.py:110-190`
- `_read_learnings`: `ce_engine/src/ce_engine/nodes.py:126-135`
- `plan_gap_node`: `ce_engine/src/ce_engine/nodes.py:332-360`
- `build_work_graph`: `ce_engine/src/ce_engine/graph.py:71-100`
- `EngineSettings`: `ce_engine/src/ce_engine/config.py:6-29`
- `WorkState`: `ce_engine/src/ce_engine/state.py:48-86`
- `ce:compound SKILL.md`: `plugins/compound-engineering/skills/ce-compound/SKILL.md`
- `ce:plan SKILL.md`: `plugins/compound-engineering/skills/ce-plan/SKILL.md`
- `learnings-researcher`: `plugins/compound-engineering/agents/research/learnings-researcher.md`
- `yaml-schema.md`: `plugins/compound-engineering/skills/compound-docs/references/yaml-schema.md`
- Existing learnings: `.context/compound-engineering/learnings/` (3 files as of 2026-03-26)

### External References

- LangGraph Checkpointing: https://langchain-ai.github.io/langgraph/how-tos/persistence/ (SqliteSaver API)
- `langgraph.checkpoint.sqlite.SqliteSaver.from_conn_string()`
