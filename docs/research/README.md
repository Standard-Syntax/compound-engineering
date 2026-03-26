# Research Repository

Standalone codebase research artifacts produced by `/ce:research`.

## Purpose

Research artifacts document what IS — the current state of the codebase — not what SHOULD BE. They capture architecture, patterns, file locations, and recent changes so future planning sessions can start from documented understanding rather than re-exploring the same code.

## Naming Convention

```
YYYY-MM-DD-slug.md
```

- `YYYY-MM-DD` — date the research was conducted
- `slug` — 3-5 words, kebab-case, derived from the research question

**Examples:**
- `2026-03-26-auth-architecture.md`
- `2026-03-26-background-jobs.md`
- `2026-03-26-skill-conventions.md`

## Frontmatter

Every artifact must include YAML frontmatter:

```yaml
---
date: 2026-03-26T10:00:00-05:00
topic: "Auth architecture research"
tags: [research, auth, security]
status: complete
git_commit: abc1234
branch: main
---
```

| Field | Description |
|-------|-------------|
| `date` | ISO 8601 timestamp when research was conducted |
| `topic` | Research question as stated |
| `tags` | Array of relevant tags for discovery |
| `status` | `complete`, `in-progress`, `stale` |
| `git_commit` | Short SHA of the commit when research was run |
| `branch` | Branch name when research was run |

## Reuse

Before conducting new research, check this directory for existing artifacts on the same topic. Recent artifacts (≤30 days) that cover your question can be reused instead of re-researching.

Use the `topic` and `tags` fields to find relevant artifacts. You can also search by date:

```bash
ls -lt docs/research/*.md | head -20
```

## Status Values

| Status | Meaning |
|--------|---------|
| `complete` | Research is finished and reviewed |
| `in-progress` | Research is underway |
| `stale` | Research may be outdated; verify before using |
