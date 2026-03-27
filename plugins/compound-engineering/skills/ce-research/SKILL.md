---
name: ce-research
description: Conduct standalone codebase research producing a compacted, reusable artifact. Use when starting a new feature, investigating an architectural question, or before planning a non-trivial change.
argument-hint: "[feature description, bug, or architectural question to research]"
---

# Standalone Codebase Research

## Purpose

Produce a standalone research artifact that documents what IS — not what SHOULD BE. The artifact is written to `docs/research/` with YAML frontmatter so it is discoverable by future planning sessions.

**Why separate from planning?** Research and planning compete for the same context window. When research sub-agents run inside the planning context, they pollute it before planning begins. A separate research phase produces a disk artifact that planning can consume in a fresh context.

## Usage

```
/ce:research [feature description, bug, or architectural question]
```

**Examples:**
```
/ce:research How does the existing auth system work?
/ce:research Background job processing patterns in ce_engine
/ce:research Adding a new compound-engineering skill — what conventions apply?
```

## Execution Flow

### Step 1: Parse Research Question

Extract the core question from the argument. If the argument is vague or missing, ask the user to clarify.

**Quality bar:** A good research question is specific enough that the answer would change how you plan. "How does auth work?" is good. "Tell me about the codebase" is not.

### Step 2: Check for Existing Research

Before spawning new research, search `docs/research/` for relevant existing artifacts:

```bash
ls docs/research/*.md 2>/dev/null | head -20
```

Check frontmatter `topic:` and `tags:` fields for relevance. If a recent (≤30 days) artifact covers the same topic, announce it and offer to use it:

> Found existing research: `docs/research/YYYY-MM-DD-topic.md` (N days ago). Use it instead of re-researching?

If the user confirms, read the existing artifact and present its findings. If not, proceed with new research.

### Step 3: Parallel Research (Sub-Agents)

Run these agents **in parallel**. Each returns text data to the orchestrator — they must NOT write files.

<parallel_tasks>

#### 1. Codebase Locator
- Task compound-engineering:research:codebase-locator({research_question})
- Returns: File and directory locations relevant to the question

#### 2. Codebase Analyzer
- Task compound-engineering:research:codebase-analyzer({research_question})
- Returns: Component interfaces, data flows, and dependencies

#### 3. Codebase Pattern Finder
- Task compound-engineering:research:codebase-pattern-finder({research_question})
- Returns: Verbatim pattern instances with file:line references

#### 4. Best Practices Researcher
- Task compound-engineering:research:best-practices-researcher({research_question})
- Returns: External best practices, relevant URLs, industry standards

#### 5. Framework Docs Researcher
- Task compound-engineering:research:framework-docs-researcher({research_question})
- Returns: Framework documentation references, Context7 findings

#### 6. Git History Analyst
- Task compound-engineering:research:git-history-analyzer({research_question})
- Returns: Recent relevant changes, historical context, file:line references

</parallel_tasks>

**Parallel dispatch limits:** 120 seconds timeout per sub-agent. If a sub-agent times out, include `status: timed_out` in the artifact and proceed with remaining agents' outputs.

**Critical:** Sub-agents must return TEXT DATA — not Write, Edit, or create files. Only the orchestrator writes the final artifact.

### Step 4: Assemble Research Artifact

After all sub-agents complete, assemble findings into a structured document.

**Output path:** `docs/research/YYYY-MM-DD-slug.md`

Where `slug` is derived from the research question — short (3-5 words), kebab-case.

**Generate git commit reference:**
```bash
git rev-parse --short HEAD
```

**Generate git branch:**
```bash
git branch --show-current
```

### Step 5: Write the Artifact

Write the complete artifact using the structure below.

---

## Research Artifact Format

```yaml
---
date: YYYY-MM-DDTHH:MM:SS+00:00
topic: "Research question as stated"
tags: [research, component-name, ...]
status: complete
git_commit: abc1234
branch: main
---

# [Research Question]

## Research Question
[Restate the question and why it matters]

## Summary
[2-3 sentence executive summary. What did the research find? What is the key takeaway?]

## Detailed Findings

### Technology & Infrastructure
[Technology stack relevant to the question, with versions if applicable]

### Architecture & Structure
[Key architectural patterns observed, with file:line references]
- `path/to/file.ext:42` — [1-line description of what this does]

### Implementation Patterns
[How existing code handles this, with file:line references]
- `path/to/file.ext:42` — [1-line description of the pattern]

### External Best Practices
[Links and key points from external research]

### Framework Documentation
[Relevant framework docs, Context7 findings]

### Recent Changes
[Git history findings relevant to this topic]

## Architecture Documentation
[Key architectural decisions observed. Document what IS — not what SHOULD BE. This section captures decisions already made in the codebase, not recommendations.]

## Code References
- `path/to/file.ext:42` — [1-line summary]
- `path/to/file.ext:100` — [1-line summary]
```

---

## Developer Review Prompt

**Required.** End every research artifact with this prompt:

```
---

## Please Review Before Proceeding

A mistake in this research cascades into the plan and then into the implementation.
Please review:
1. Are the file:line references accurate?
2. Is the architecture description correct?
3. Are there any misconceptions or gaps?

Reply with corrections or "looks good" before proceeding to planning.
```

---

## Naming Convention

| Element | Format | Example |
|---------|--------|---------|
| Directory | `docs/research/` | `docs/research/` |
| Filename | `YYYY-MM-DD-slug.md` | `docs/research/2026-03-26-auth-architecture.md` |
| Slug | 3-5 words, kebab-case | `auth-architecture`, `background-jobs`, `skill-conventions` |

---

## Key Principles

1. **Document what IS, not what SHOULD BE.** This is pure documentation. No recommendations, no opinions, no "you should".
2. **Every codebase claim needs a file:line reference.** If you can't point to the code, don't claim it.
3. **Sub-agents return text; orchestrator writes files.** Sub-agents must NOT use Write, Edit, or create files.
4. **Research is reusable, not一次性.** Write artifacts as if a future developer who has never seen this codebase will read them.

## Common Mistakes

| ❌ Wrong | ✅ Correct |
|----------|-----------|
| Sub-agents write their own `.md` files | Orchestrator collects text and writes one file |
| "You should use Redis for this" | "The codebase currently uses X for this purpose (file:line)" |
| Research artifact has no frontmatter | YAML frontmatter with date, topic, tags, status, git_commit, branch |
| Research artifact ends without review prompt | Required developer review prompt at end |
| Re-researching a topic already covered | Check `docs/research/` first; reuse if recent |
