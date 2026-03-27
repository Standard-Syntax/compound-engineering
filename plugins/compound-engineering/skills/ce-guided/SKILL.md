---
name: ce:guided
description: "Guided compound engineering workflow with mandatory human gates between each phase: research -> plan -> work -> review -> compound. Use for complex or brownfield tasks where human oversight at decision points is worth the time."
argument-hint: "[feature description]"
disable-model-invocation: false
---

# /ce:guided — Guided Compound Engineering Workflow

Orchestrates the full CE pipeline with a human in the loop at every phase boundary. Independent commands pass state via a session manifest. Use when autonomous workflows (`/lfg`, `/slfg`) are too fast and you want to review each phase before committing to the next.

## Interaction Method

Use the platform's blocking question tool when available (`AskUserQuestion` in Claude Code, `request_user_input` in Codex, `ask_user` in Gemini). Present gate choices as numbered options. Wait for user input before proceeding.

When the blocking question tool is unavailable, present numbered options in chat and wait for the user's reply before proceeding.

---

## Session Manifest Pattern

Each guided session maintains a manifest file so independent commands pass state:

```
.context/compound-engineering/guided-sessions/<uuid>/manifest.json
```

```json
{
  "session_id": "<uuid>",
  "started_at": "ISO8601",
  "research_artifact": null,
  "plan_path": null,
  "work_branch": null,
  "review_output": null,
  "solution_path": null,
  "status": "in_progress"
}
```

**Atomic writes:** Write to `.tmp` file first, then rename to target path. This prevents state corruption if the write fails mid-operation.

**Session recovery:** If a session is abandoned mid-flow, resume by invoking `/ce:guided --resume <uuid>`.

---

## Gate Design Principles

Per human-in-the-loop best practices:

1. **Stop to wait** — each gate uses the blocking question tool. The orchestrator pauses and waits for input before proceeding.
2. **Evidence first** — before each gate, gather evidence and present a structured summary. The human decides with context, not blind.
3. **No contradictory rules** — gate choices are consistent across all phases.
4. **Non-contradictory resume** — if the orchestrator resumes, gate state is consistent with where it left off.

---

## Gate Presentation Format

At each gate, present a structured summary (not the full artifact):

```
## Gate: [Phase Name] Complete

**Artifact:** `path/to/artifact.md`
**Status:** [complete / incomplete]

### Evidence
- **Topic:** [from frontmatter]
- **Tags:** [from frontmatter]
- **Files referenced:** [count from research artifact]
- **Phases:** [count from plan artifact]

### Key Findings
[3-5 bullet points auto-generated from artifact body]

### What changed since last gate
[1-2 sentences on what was done in this phase]
```

**Blocking question:**
> "Ready at `path/to/artifact.md`. Review the evidence above. How would you like to proceed?"

Choices:
1. **Proceed** — move to the next phase
2. **Revise this phase** — re-run the current phase (overwrites the artifact)
3. **Exit session** — abandon the session

If the user chooses **Revise**, re-run the same phase with the same arguments.

---

## Orchestration Flow

```
/ce:guided <topic>
  │
  ├─ Generate session UUID
  ├─ Create manifest at .context/.../<uuid>/manifest.json
  │
  ├─ Run /ce:research <topic>
  │     └─ Write artifact path → manifest.research_artifact
  │
  ├─ GATE 1: Research Review
  │     ├─ Proceed → next
  │     ├─ Revise → re-run ce:research
  │     └─ Exit → end session
  │
  ├─ Run /ce:plan with research artifact in arguments
  │     └─ Write plan path → manifest.plan_path
  │
  ├─ GATE 2: Plan Review
  │     ├─ Proceed → next
  │     ├─ Revise → re-run ce:plan
  │     └─ Exit → end session
  │
  ├─ Run /ce:work <plan_path>
  │     └─ Write branch name → manifest.work_branch
  │     (Note: /ce:work has its own internal phase gates)
  │
  ├─ GATE 3: Post-Implementation Review
  │     ├─ Proceed → next
  │     ├─ Continue working → re-enter /ce:work
  │     └─ Exit → end session (artifacts persist)
  │
  ├─ Run /ce:review <branch_name>
  │     └─ Write review output → manifest.review_output
  │
  ├─ GATE 4: Review Findings
  │     ├─ Document → next
  │     ├─ Skip → end session
  │     └─ Exit → end session
  │
  └─ Run /ce:compound
        └─ Write solution path → manifest.solution_path
              └─ End session
```

---

## Command Invocation Formats

Each phase invokes an existing CE command. The invocation must match what the target skill actually accepts:

| Phase | Command | Invocation | Notes |
|-------|---------|------------|-------|
| 1 | `/ce:research` | `/ce:research $ARGUMENTS` | No changes needed |
| 2 | `/ce:plan` | `/ce:plan $ARGUMENTS` | Pass research artifact path in argument text. `ce:plan` Step 0.5 already parses this. |
| 3 | `/ce:work` | `/ce:work docs/plans/YYYY-MM-DD-NNN-*-plan.md` | Pass plan path as argument. No `--sub-mode` flag. |
| 4 | `/ce:review` | `/ce:review $BRANCH_NAME [--serial]` | `ce:review` is PR/branch-centric. Pass branch name. |
| 5 | `/ce:compound` | `/ce:compound` | No arguments needed |

**Important:** `/ce:plan` does not have a `--research` flag. Pass research artifact path as part of the argument text:
```
/ce:plan <topic>

Research: docs/research/YYYY-MM-DD-slug.md
```

---

## Double-Gating Resolution

`/ce:work` uses `human_interrupt_node` in the LangGraph engine, which calls `langgraph.types.interrupt()`. This is a core graph mechanism — there is no flag to disable it.

Gate 3 (Post-Implementation Review) is the guided-mode gate. `/ce:work` runs with its normal internal gates intact. The human pauses twice per implementation phase (guided gate + work gate) — conservative but correct.

---

## Session Initialization

### Normal Start

1. Generate session UUID
2. Create manifest directory: `.context/compound-engineering/guided-sessions/<uuid>/`
3. Write manifest with `status: in_progress` (atomic write: write to `.tmp`, then rename)
4. Announce: "Starting guided session `[uuid]`. I'll pause at each phase for your review."

### Resume

If invoked with `--resume <uuid>`:
1. Read manifest from `.context/compound-engineering/guided-sessions/<uuid>/manifest.json`
2. Identify the last completed phase from manifest fields
3. Offer to continue from there

---

## Phase 1: Research

Run `/ce:research $ARGUMENTS`

After completion:
- Locate the research artifact (use `ls docs/research/*.md | tail -1` to find the most recent)
- Update manifest: `research_artifact` = path to produced artifact (atomic write)
- Proceed to Gate 1

---

## Gate 1: Research Review

Read the research artifact. Generate a structured summary:
- Extract `topic`, `tags`, `date`, `git_commit` from frontmatter
- Count `## Code References` entries → "N files referenced"
- Read `## Summary` section → use first 3 bullets

If the artifact is missing required sections (`topic`, `## Summary`, `## Code References`), note "Incomplete" in the status.

Present the structured gate format. Block with the platform's question tool.

---

## Phase 2: Planning

Run `/ce:plan` with the research artifact path in the argument text:
```
/ce:plan <original topic>

Research: docs/research/YYYY-MM-DD-slug.md
```

After completion:
- Locate the plan artifact (use `ls docs/plans/*.md | tail -1` to find the most recent)
- Update manifest: `plan_path` = path to produced plan (atomic write)
- Proceed to Gate 2

---

## Gate 2: Plan Review

Read the plan artifact. Generate a structured summary:
- Extract `title`, `type`, `date` from frontmatter
- Count `## Acceptance Criteria` checklist items
- Count `## Implementation Phases` sub-sections
- Read `## What We're NOT Doing` → list items

Present the structured gate format. Block with the platform's question tool.

---

## Phase 3: Implementation

Run `/ce:work <plan_path>`

`/ce:work` executes the plan with its own internal `human_interrupt_node` phase gates. These fire independently of the guided-mode gates.

After `/ce:work` completes:
- Determine the branch name used: `git branch --show-current`
- Update manifest: `work_branch` = branch name (atomic write)
- Proceed to Gate 3

---

## Gate 3: Post-Implementation Review

Read the plan file. Count completed vs. pending checkboxes. Extract any `## Key Decisions` noted during work.

Present the structured gate format. Block with the platform's question tool.

Choices at this gate differ slightly:
1. **Proceed** → next (to review)
2. **Continue working** → re-enter `/ce:work` with the same plan path
3. **Exit** → end session (artifacts persist)

---

## Phase 4: Review

Run `/ce:review <branch_name>` where `branch_name` is from `manifest.work_branch`.

After completion:
- Update manifest: `review_output` = summary of review findings (atomic write)
- Proceed to Gate 4

---

## Gate 4: Review Findings

Count total findings by severity. List top 3 high-severity findings.

Present the structured gate format. Block with the platform's question tool.

Choices:
1. **Document** → next (to compound)
2. **Skip** → end session without documenting
3. **Exit** → end session

---

## Phase 5: Compound

Run `/ce:compound`

After completion:
- Locate the solution document (use `ls docs/solutions/*.md | tail -1` to find the most recent)
- Update manifest: `solution_path` = path to produced solution doc (atomic write)
- Set manifest `status: completed`
- Announce session summary

---

## Session End

Output:
```
## Guided Session Complete

**Session ID:** `<uuid>`
**Artifacts:**
- Research: `docs/research/...`
- Plan: `docs/plans/...`
- Solution: `docs/solutions/...`
```

---

## Error Handling

| Error | Response |
|-------|----------|
| `/ce:research` fails | Gate 1 pauses. User can revise arguments and re-run, or exit. |
| `/ce:plan` fails repeatedly | Gate 2 pauses. User can revise arguments or exit. |
| `/ce:work` fails | Normal `/ce:work` error handling. User can resume. |
| Manifest write fails | Abort session. Do not proceed with unclear state. |
| `--resume <uuid>` not found | Announce error and offer to start a new session. |

---

## Key Principles

1. **Manifest is the single source of truth** — all phase transitions update the manifest first
2. **Atomic writes prevent corruption** — always write to `.tmp` then rename
3. **Evidence before decision** — never ask a gate question without presenting context first
4. **Artifacts persist** — even if a session is abandoned, artifacts in `docs/` remain
5. **Conservative gates** — double-pause at implementation is intentional; extra review is better than skipped review
