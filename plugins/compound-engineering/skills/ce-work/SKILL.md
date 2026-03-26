---
name: ce:work
description: Execute work plans efficiently while maintaining quality and finishing features
argument-hint: "[plan file, specification, or todo file path]"
---

# Work Plan Execution

## Recommended Approach: LangGraph Engine (`ce-work` CLI)

The canonical implementation for work execution is the LangGraph engine, invoked via the `/ce:work` command or directly as the `ce-work` CLI.

### What the Engine Does

1. Reads the active plan from `.context/compound-engineering/plan/`
2. Builds a Context Pack (runs ruff, ty, reads learnings)
3. Runs the LangGraph work engine with the active task
4. Pauses for your input on blocked or risky operations
5. Writes a compact error delta after each iteration
6. Stops when the task is done or the iteration limit is reached

### Phase Tracking and Verification Gates

The engine supports phase-by-phase implementation with manual verification gates:

- **Phase tracking:** The engine tracks `current_phase` in its state. When the LLM outputs `[PHASE_COMPLETE]` in its response text (not JSON), the engine routes to the `phase_compact_node`.
- **Verification gates:** After each phase, the engine checks the plan file for Manual Verification items. If items exist, the engine pauses via `human_interrupt_node` and waits for human confirmation before proceeding.
- **Compaction:** When the LLM outputs `[COMPACT]` in its response text, the engine writes a structured progress summary to the plan file and resets the file-read counter.
- **Context budget:** The engine tracks files read directly; if more than 15 files have been read, the LLM is prompted to compact. Keep context utilization in the 40-60% range.

**Plan file format for phases:** Use `### Manual Verification` heading under each phase to list items that require human verification. The engine scans for this heading to determine when to pause.

### Usage

**Start a new work session:**
```
ce-work "<task_description>" "<path to plan file>"
```

**Resume a paused session:**
```
ce-work "<task_description>" "<path to plan file>" <session-id>
```

The `/ce:work` command is the primary interface - it handles session tracking and coordinates with the engine automatically. Use the `ce-work` CLI directly only when you need fine-grained control over the session lifecycle.

### Session Management

- Sessions are identified by a UUID printed at the start of each run
- Pass the session ID as the third argument to resume an interrupted session
- The engine will pause and ask for input when it encounters blocked operations, risky operations, or plan gaps
- After each iteration, it writes a compact error delta so you can track what changed

### Constraints

- Never start a work session without a plan file present
- Always report the session ID so you can resume if needed

---

## Deprecated: Inline/Subagent Approach

The inline/subagent execution strategy described below is **deprecated**. It is retained for reference only and will be removed in a future version.

The deprecated approach involved:
- Reading the work document completely and creating a task list manually
- Choosing between inline, serial subagent, or parallel subagent execution
- Managing task execution loops, incremental commits, and branch creation manually
- Running Phase 1 (Quick Start), Phase 2 (Execute), Phase 3 (Quality Check), and Phase 4 (Ship It) steps manually

If you need the old behavior for compatibility reasons, it is preserved in the git history. New work should use the LangGraph engine approach described above.
