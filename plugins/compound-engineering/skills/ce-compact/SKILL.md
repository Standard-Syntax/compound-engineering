---
name: ce-compact
description: Produce a structured compaction summary for resuming work in a new context window. Use when context is getting heavy, before switching tasks, or when pausing a work session.
argument-hint: "[optional: output path for compaction summary]"
---

# Compaction Summary

## Purpose

Produce a structured summary of the current work session that is sufficient to resume in a new context window with no additional background. Write the summary to disk so another context can cold-start from it.

**When to use:**
- Context utilization is approaching 60% and the current task is not complete
- Switching to a different task and the current work needs to be preserved
- Pausing a work session; want a checkpoint before resuming
- Before running a long sub-agent operation that will fill context

## Usage

```
/ce:compact                          # Write to default: .context/compound-engineering/compact-TIMESTAMP.md
/ce:compact path/to/summary.md       # Write to custom path
```

## Steps

### 1. Determine Output Path

If the user provided an output path as the argument, use it. Otherwise, generate a timestamped default:

```bash
date +%Y%m%d-%H%M%S
```

Output to: `.context/compound-engineering/compact-YYYYMMDD-HHMMSS.md`

Create the directory if needed:
```bash
mkdir -p .context/compound-engineering/
```

### 2. Read Plan File (if exists)

Check if there is a plan file for the current work:
```bash
ls .context/compound-engineering/plan/*.md 2>/dev/null | head -5
```

If a plan file exists, read it to understand:
- The overall goal
- Which tasks are complete vs. pending
- Current phase (if using phase-based planning)

### 3. Read Recent Context

From the conversation history, identify:
- What was the last thing worked on?
- What files were modified or created?
- What errors or blockers were encountered?
- What decisions were made?

### 4. Write the Compaction Summary

Write the following structure to the output file:

```markdown
## Compaction Summary

### Goal
[What we're trying to accomplish]

### Approach
[Strategy being used]

### Completed Steps
- [Step 1 with outcome]
- [Step 2 with outcome]
- [Step N with outcome]

### Current Status
[Where we are now, including any failures or blockers]

### Relevant Files
- `path/to/file.ext` — [1-line summary of role]
- `path/to/file.ext` — [1-line summary of role]

### Key Decisions
- [Decision and rationale]

### Next Steps
- [What remains]
- [Immediate next action]
```

**Key constraints:**
- Write for a reader who has zero context about this session
- Every section is required — if there's nothing to put in a section, write "None" rather than omitting
- `Relevant Files` must have `path:line` or `path` format — not vague descriptions
- `Next Steps` must be specific and actionable, not vague

### 5. Confirm Output

After writing, display:
```
✓ Compaction complete

Written to: .context/compound-engineering/compact-20260326-143052.md

This summary is sufficient to resume work in a new context window.
To resume: read the compaction file first, then continue with Next Steps.
```

## Key Principles

1. **Compaction = structured summary written to disk.** It is not just remembering — it produces a file that another context window can cold-start from.
2. **Write for a cold reader.** A future reader with no context must be able to understand the goal, what's done, what's left, and what files matter.
3. **Relevant Files are specific.** Use `path/to/file.ext` format, not "the main service file".
4. **Next Steps are actionable.** "Continue implementation" is not actionable. "Run `ce-work` with session ID `abc-123`" is actionable.

## Common Mistakes

| ❌ Wrong | ✅ Correct |
|----------|-----------|
| "See above for context" | Full summary written to disk for cold resume |
| "Various files were modified" | `src/auth/service.rb:42` — handles JWT validation |
| "Keep working on the feature" | "Next: add `auth_service.verify_token()` call to `api/v1/sessions.py:15`" |
| Section omitted because empty | Write "None" — preserves structure for future editing |
