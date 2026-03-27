---
title: "Code Review Learning: Schema Validation for Agent JSON Output"
category: skill-design
date: 2026-03-26
tags: [code-review, schema-validation, research-agents, ce-guided, multi-agent-review, agent-authoring]
status: completed
related_pr: "6"
pr_title: "feat: add /ce:guided orchestrator and sub-agent specialization"
---

# Code Review Learning: Schema Validation for Agent JSON Output

## Problem

PR #6 added three new research agents (`codebase-locator`, `codebase-analyzer`, `codebase-pattern-finder`) and a new `/ce:guided` orchestrator skill. A systematic multi-agent code review found 10 findings (1 P1, 8 P2, 1 P3). Eight of those findings were schema inconsistencies — documented behaviors missing from the JSON output schemas, prose fields with no structured definition, and contradictory definitions between constraint text and schema.

All 10 findings were resolved in the same PR via parallel `pr-comment-resolver` subagents — one agent per finding, all running simultaneously.

## Root Cause

When agents are first created, their JSON output schemas are written once but the constraint text evolves independently. The schema and the text descriptions drift. Five failure classes appeared:

1. **Schema incompleteness** — `status` fields listed only `complete` when `partial` and `error` are valid terminal states; `side_effects` used freeform string syntax instead of a proper enum
2. **Skill frontmatter omissions** — `agent_native: false` missing from a non-agent-native skill
3. **Nonstandard dispatch syntax** — `Scope:` prefix on Task calls diverged from the standard convention
4. **Type mismatch in manifest schema** — `review_output` declared as `string` but `/ce:review` produces a structured `{p1, p2, p3}` object
5. **Constraint blind spots** — parallel-session hazards not documented at artifact discovery points

## Solution

Eight fix commits applied simultaneously by parallel `pr-comment-resolver` subagents:

### 1. `codebase-locator` — `status: partial` added to schema

```json
// Before
"status": "complete",

// After
"status": "complete | partial",
```

File: `agents/research/codebase-locator.md`

### 2. `codebase-analyzer` — `status: error` and `error` field added

```json
// Before
"status": "complete",

// After
"status": "complete | error",
"error": "<error message if status is error>",
```

File: `agents/research/codebase-analyzer.md`

### 3. `codebase-analyzer` — `side_effects` changed to structured enum

```json
// Before
"side_effects": "none | reads: X | writes: Y | network: Z"

// After
"side_effects": "none | reads | writes | network | mixed"
```

File: `agents/research/codebase-analyzer.md`

### 4. `codebase-pattern-finder` — similarity evaluation criteria documented

```json
// Before
"similarity": "high | medium | low"

// After
"similarity": "high | medium | low" // high: nearly identical code structure; medium: same intent but different variable names or minor structural differences; low: loosely related pattern, same general approach
```

File: `agents/research/codebase-pattern-finder.md`

### 5. `ce-guided` — `agent_native: false` added to frontmatter

```yaml
---
name: ce:guided
description: "Guided compound engineering workflow... Note: this workflow requires human input at each gate and cannot run autonomously."
argument-hint: "[feature description]"
disable-model-invocation: false
agent_native: false
---
```

File: `skills/ce-guided/SKILL.md`

### 6. `ce-research` — nonstandard `Scope:` prefix removed from Task dispatch

```markdown
// Before
Task compound-engineering:research:codebase-locator(Scope: technology, architecture. {research_question})

// After
Task compound-engineering:research:codebase-locator({research_question})
```

Files: `skills/ce-research/SKILL.md`, `skills/ce-research-beta/SKILL.md`

### 7. `ce-guided` — parallel-session constraint documented

Added at each artifact discovery point in `ce-guided/SKILL.md`:

```markdown
> **Constraint:** Do not run parallel manual `/ce:research`, `/ce:plan`, or `/ce:compound` sessions while a guided session is active.
```

### 8. `ce-guided` — `manifest.review_output` changed from string to structured `{p1, p2, p3}`

```json
// Before
"review_output": null  // summary of review findings (string)

// After
"review_output": null  // {"p1": N, "p2": M, "p3": K} — populated after Phase 4
```

File: `skills/ce-guided/SKILL.md`

## Prevention Strategies

### Schema-Text Consistency for Agent JSON Outputs

The JSON schema block and prose descriptions must be written together and reviewed as a unit. Every enum value in the schema must have a corresponding prose explanation. Key actions:

- Add `<!-- AUTHORITATIVE SCHEMA -->` marker block at top of Output Format section
- Every enum value in schema must have corresponding prose explanation
- Add schema-lint check that verifies all documented states appear in the schema and vice versa

### Skill Frontmatter Completeness

Always set `agent_native: false` for skills that require human input at gates; include that constraint in the description field.

### Task Dispatch Argument Formats

Never prefix arguments with nonstandard labels like `Scope:`; pass structured context as inline text or separate fields. Valid dispatch format:

```markdown
Task compound-engineering:research:codebase-locator({research_question})
```

### Manifest Field Types

Mirror the actual output type of the tool that populates each field. If `/ce:review` returns `{p1, p2, p3}`, the manifest field must be typed as a structured object, not a string.

### Artifact Discovery Robustness

Never use `ls docs/X/*.md | tail -1` to discover artifacts. Use manifest-driven paths or session-scoped directories. Document interaction constraints at every point where a workflow reads or writes shared state.

### Verification Commands

```bash
# Check for fragile ls | tail -1 patterns
grep -rn 'ls.*|.*tail -1' plugins/compound-engineering/skills/

# Check for undocumented status values in agent schemas
grep -rn 'status:' plugins/compound-engineering/agents/research/

# Check for Scope: prefix usage
grep -rn 'Scope:' plugins/compound-engineering/skills/
```

## Related Documentation

- `docs/solutions/skill-design/script-first-skill-architecture.md` — Token optimization for agent authoring
- `docs/solutions/skill-design/compound-refresh-skill-improvements.md` — Subagent dispatch patterns
- `docs/solutions/skill-design/beta-skills-framework.md` — Safe rollout patterns for new skills
- `docs/solutions/code-quality/python-engine-review-patterns.md` — General code review patterns

## Commits

| Commit | Fix |
|--------|-----|
| `b2d0927` | `codebase-locator`: `status: partial` added to schema |
| `e4b64bd` | `codebase-analyzer`: `side_effects` changed to structured enum |
| `2eff1e5` | `ce-guided`: `agent_native: false` added to frontmatter |
| `5a9fc6b` | `codebase-pattern-finder`: similarity evaluation criteria added |
| `b3eaf24` | `codebase-analyzer`: `status: error` and `error` field added |
| `0e5d31d` | `ce-guided`: parallel-session constraint documented |
| `cdb0ffe` | `ce-research`: removed nonstandard `Scope:` prefix from Task dispatch |
| `595afba` | `ce-guided`: `manifest.review_output` now structured `{p1, p2, p3}` |

## Items Deferred

- **Name convention mismatch** (`ce:guided` vs `ce-guided`): Pre-existing issue across all `ce:` skills. Deferred to cleanup PR for all `ce:` skill name conventions.
