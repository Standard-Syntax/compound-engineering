---
name: calibrate
description: Record the difference between estimated and actual task duration for iteration planning
argument-hint: ""
version: "1.0.0"
triggers: ["ce:calibrate", "calibrate"]
---

# Record estimation accuracy for iteration planning

## Introduction

Record the difference between how long a task was estimated to take and how long it actually took. Run this immediately after `/ce:work` finishes a task.

**Note: The current year is 2026.**

## Steps

### 1. Find the completed task

Read the plan file from `.context/compound-engineering/plan/`. Find the task that was just completed.

### 2. Read work session output

Read the work session output to determine:
- Number of iterations actually used (read from thread.db if possible, otherwise ask the user)
- Number of times the loop paused for human input
- Whether any plan gaps were logged in `.context/compound-engineering/plan-gaps.md`

### 3. Ask the user questions

Ask the user these two questions:
- "How many iterations did you expect this task to take?"
- "Was the complexity higher, lower, or as expected?"

### 4. Write the calibration record

Write a calibration record to `.context/compound-engineering/calibrations/YYYY-MM-DD-<task-slug>.md` using this template:

```markdown
## Calibration: <task title>

**Date:** <YYYY-MM-DD>
**Plan estimate:** <user's answer to question 1>
**Actual iterations:** <from work session>
**Human interrupts:** <count>
**Plan gaps found:** <yes with count, or no>
**Complexity:** <higher / lower / as expected>
```

### 5. Add bias alert if needed

If the actual iteration count exceeded the estimate by 2 or more, append:

```markdown
**Bias alert:** Underestimated by <N> iterations.
Add 2 iterations to future estimates for similar tasks.
```
