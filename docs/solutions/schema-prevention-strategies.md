# Schema Drift Prevention Strategies

**Date:** 2026-03-26
**Topic:** Preventing agent JSON output schema drift from constraint/implementation text
**Root Cause:** When agents are first created, their JSON output schemas are written once but the constraint/implementation text evolves independently, causing schema and text descriptions to diverge.

---

## Issues Summary

| # | Issue | Agents Affected |
|---|---|---|
| 1 | `status: partial` and `status: error` documented but missing from schema | `codebase-locator`, `codebase-analyzer` |
| 2 | `side_effects` mixed prose and structured data in same field | `codebase-analyzer` |
| 3 | `similarity` values had no evaluation criteria | `codebase-pattern-finder` |
| 4 | `context` field had contradictory definitions in different sections | Multiple agents |
| 5 | Artifact discovery relied on `ls \| tail -1` (fragile under concurrency) | `ce-guided` |
| 6 | Task dispatch used nonstandard `Scope:` prefix | `repo-research-analyst` |

---

## Strategy 1: Schema-Text Consistency for Agent JSON Outputs

### Core Principle
The JSON schema section and the prose constraints MUST be written together and reviewed as a single unit. Neither can evolve independently.

### Actionable Steps

#### 1.1 Co-located Schema Block Pattern
Every agent SKILL.md that produces JSON output MUST have a single, authoritative schema block that appears:
1. At the top of the Output Format section
2. In a clearly marked JSON code fence with a comment: `<!-- AUTHORITATIVE SCHEMA -->`

```markdown
## Output Format

<!-- AUTHORITATIVE SCHEMA - This block is the single source of truth.
     All prose descriptions must reference these exact field names and values. -->
```json
{
  "agent": "codebase-analyzer",
  "status": "complete | error | partial",
  "error": "<error message if status is error>",
  "components": [...]
}
```
<!-- /AUTHORITATIVE SCHEMA -->

All prose in Constraints and Execution sections MUST use the exact field names from this block.
```

#### 1.2 Schema Review Checklist
Before merging any agent modification, verify:

- [ ] Every `status` value documented in prose appears in the JSON schema
- [ ] Every enum value in the schema has an accompanying prose explanation
- [ ] Every field mentioned in prose is defined in the schema
- [ ] `side_effects` enum values are described in prose (not mixed with description)
- [ ] Similarity thresholds are explicit in prose (e.g., "high = >90% token overlap")

#### 1.3 Automated Schema-Text Linting
Add a ruff-based check that extracts JSON schema blocks and verifies:
- All enum values are documented
- Field order in prose matches schema order
- No phantom fields in prose that don't exist in schema

```python
# .github/lint/schema-text-lint.py
import re
from pathlib import Path

def lint_agent_schemas(repo_root: Path) -> list[str]:
    """Lint all agent SKILL.md files for schema-text consistency."""
    errors = []
    for skill_file in repo_root.glob("plugins/compound-engineering/skills/*/SKILL.md"):
        content = skill_file.read_text()
        schema = _extract_schema_block(content)
        prose_fields = _extract_prose_fields(content)
        # Check for undocumented enum values
        for enum_field, values in schema.enums.items():
            for value in values:
                if value not in prose_fields.get(enum_field, []):
                    errors.append(f"{skill_file}: {enum_field}.{value} documented but not in prose")
        # Check for phantom fields
        for field in prose_fields:
            if field not in schema.fields:
                errors.append(f"{skill_file}: '{field}' in prose but not in schema")
    return errors
```

#### 1.4 Test Scenarios

| Scenario | Input | Expected Behavior |
|---|---|---|
| Agent outputs `status: partial` | `codebase-locator` returns after 5 rounds | Schema accepts `partial`; prose documents it |
| Agent outputs unknown status | `codebase-locator` returns `status: unknown` | Parser rejects; CI fails |
| Prose mentions `side_effects: reads` | Constraint text says "reads = reads files" | Schema enum has `reads` |
| Prose references `context` field | Analyzer output references `context` field | Schema defines `context` with type |

---

## Strategy 2: Artifact Discovery Robustness

### Core Principle
Never use `ls \| tail -1` or other ordering-dependent commands for artifact discovery. Artifacts must be explicitly tracked via manifests or predictable naming conventions.

### Issues Found
```markdown
# ce-guided/SKILL.md lines 194, 224, 300
- Locate the research artifact (use `ls docs/research/*.md | tail -1` to find the most recent)
```

This is fragile because:
1. Two concurrent runs can produce artifacts in the same second
2. Alphabetical sorting may not match temporal ordering
3. Manual edits can change file modification times

### Actionable Steps

#### 2.1 Manifest-Driven Discovery (Required)
All multi-phase workflows MUST use manifest files that explicitly record artifact paths:

```json
// .context/compound-engineering/guided-sessions/<uuid>/manifest.json
{
  "research_artifact": "docs/research/2026-03-26-topic-slug.md",
  "plan_path": "docs/plans/2026-03-26-001-topic-slug-plan.md",
  "solution_path": null,
  "status": "phase_2_complete"
}
```

Phase completion MUST update manifest atomically:
```bash
# WRONG - fragile
ls docs/research/*.md | tail -1

# RIGHT - manifest-driven
jq ".research_artifact = \"$path\" | .status = \"phase_1_complete\"" manifest.json > tmp && mv tmp manifest.json
```

#### 2.2 Predictable Naming Convention
Use date-stamped slugs that are deterministic:

```bash
# Generate predictable path from inputs (no discovery needed)
TOPIC_SLUG=$(echo "$ARGUMENTS" | slugify)
TODAY=$(date +%Y-%m-%d)
RESEARCH_PATH="docs/research/${TODAY}-${TOPIC_SLUG}.md"
PLAN_PATH="docs/plans/${TODAY}-001-${TOPIC_SLUG}-plan.md"
```

#### 2.3 Atomic Manifest Updates
Use temporary files + rename for atomicity:

```python
import json
from pathlib import Path

def update_manifest(manifest_path: Path, updates: dict) -> None:
    """Atomically update manifest fields."""
    tmp = manifest_path.with_suffix('.tmp')
    current = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    current.update(updates)
    tmp.write_text(json.dumps(current, indent=2))
    tmp.rename(manifest_path)  # Atomic on POSIX
```

#### 2.4 Test Scenarios

| Scenario | Setup | Expected Behavior |
|---|---|---|
| Concurrent guided sessions | Two sessions started within same second | Each writes to different manifest; no path collision |
| Resume after crash | Manifest exists with `research_artifact` set | Resume reads manifest, not filesystem |
| Manual artifact deletion | User deletes research artifact | Manifest still has old path; error on resume with clear message |
| Runner discovers artifact | After `/ce:research` completes | Uses manifest path, not `ls \| tail -1` |

---

## Strategy 3: Cross-Skill Handoff Argument Formats

### Core Principle
Agent dispatch arguments must use explicit, validated key-value pairs rather than ad-hoc prefixes or conventions that aren't machine-readable.

### Issues Found

#### 3.1 Nonstandard `Scope:` Prefix
```markdown
# repo-research-analyst.md line 42
When the input begins with `Scope:` followed by a comma-separated list, run only the phases that match the requested scopes.
```

This is problematic because:
- `Scope:` is not a standard dispatch format
- No schema validates the scope values
- Consuming skills hard-code string matching

#### 3.2 Alternatives Considered

| Format | Pros | Cons |
|---|---|---|
| `Scope: technology, patterns` | Human readable | Not machine-parseable without regex |
| `{"scope": ["technology", "patterns"]}` | Machine readable, validatable | Less natural in chat context |
| `SCOPE=technology,patterns` | Unambiguous prefix | Requires parsing logic |

### Recommended Approach: Structured Dispatch Format

#### 3.3 Structured Dispatch with Schema-Validated Scopes

```markdown
## Dispatch Format

When invoking this agent from a skill or command, use this structured format:

```
INVOKE compound-engineering:research:repo-research-analyst
SCOPE: technology, architecture, patterns
INPUT: We are building a new background job processor for the billing service.
```

Where `SCOPE` values are validated against:

| Scope | Valid Values |
|---|---|
| scope | `technology`, `architecture`, `patterns`, `conventions`, `issues`, `templates` |
| input | Free text describing the research context |

If `SCOPE:` is absent, run all phases (default behavior).

The agent parses `SCOPE:` prefix followed by comma-separated values.
```

#### 3.4 Standardized Dispatch Schema

Add to `subagent-dispatch-protocol/SKILL.md`:

```markdown
## Standard Dispatch Prefixes

All agent dispatches MUST use these prefixes consistently:

| Prefix | Purpose | Format |
|--------|----------|--------|
| `SCOPE:` | Phase/scope selection | `SCOPE: phase1, phase2` (comma-separated) |
| `INPUT:` | Primary argument | `INPUT: <free text>` |
| `CONTEXT:` | Additional context | `CONTEXT: <path to file>` |

No other dispatch prefixes are allowed. Agents that need custom prefixes
MUST register them in the dispatch protocol skill before use.
```

#### 3.5 Test Scenarios

| Scenario | Input | Expected Behavior |
|---|---|---|
| Valid scope dispatch | `SCOPE: technology, patterns` | Agent runs phases for those scopes only |
| Invalid scope value | `SCOPE: invalid_scope` | Agent returns error with valid scopes listed |
| No scope (default) | No `SCOPE:` line | Agent runs all phases |
| Multiple scopes | `SCOPE: technology, architecture, patterns` | All three phases run |
| Scope with whitespace | `SCOPE: technology , patterns` | Normalized: `["technology", "patterns"]` |

---

## Implementation Plan

### Phase 1: Immediate Fixes (This PR)

1. **Fix `codebase-locator` schema** - Add `status: partial` and `status: error` to JSON schema block
2. **Fix `codebase-analyzer` schema** - Add `status: error` and `status: partial`; clarify `side_effects` enum
3. **Fix `codebase-pattern-finder` schema** - Add evaluation criteria for `similarity` values in prose
4. **Fix `ce-guided` artifact discovery** - Replace `ls | tail -1` with manifest-driven paths
5. **Document `Scope:` dispatch** - Add to `subagent-dispatch-protocol` with validation rules

### Phase 2: Infrastructure (Next Sprint)

1. Add schema-lint CI check for agent SKILL.md files
2. Add dispatch format validation to subagent-dispatch-protocol
3. Create `scripts/lint-agent-schemas.py` for local validation

### Phase 3: Process (Ongoing)

1. Add schema-text consistency checklist to PR review guidelines
2. Document the "AUTHORITATIVE SCHEMA" block pattern
3. Add to agent creation template

---

## Files Affected

| File | Change | Issue |
|---|---|---|
| `skills/codebase-locator/SKILL.md` | Add `status: partial` to schema | #1 |
| `skills/codebase-analyzer/SKILL.md` | Add `status: error` to schema; clarify `side_effects` | #1, #2 |
| `skills/codebase-pattern-finder/SKILL.md` | Document `similarity` evaluation criteria | #3 |
| `skills/ce-guided/SKILL.md` | Replace `ls \| tail -1` with manifest-driven paths | #5 |
| `skills/subagent-dispatch-protocol/SKILL.md` | Add `SCOPE:` dispatch standard | #6 |
| `agents/research/repo-research-analyst.md` | Update to use standard `SCOPE:` prefix | #6 |

---

## Verification Commands

```bash
# Check for ls | tail -1 patterns in skills
grep -rn 'ls.*|.*tail -1' plugins/compound-engineering/skills/

# Check for undocumented status values in agent schemas
grep -rn 'status:' plugins/compound-engineering/agents/ | grep -v 'status: complete | error | partial'

# Check for Scope: prefix usage
grep -rn 'Scope:' plugins/compound-engineering/
```
