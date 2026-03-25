# /ce:work

Execute the work loop for the current plan task.

## What This Does

1. Reads the active plan from `.context/compound-engineering/plan/`.
2. Builds a Context Pack (runs ruff, ty, reads learnings).
3. Runs the LangGraph work engine (`ce-work` CLI) with the active task.
4. Pauses for your input on blocked or risky operations.
5. Writes a compact error delta after each iteration.
6. Stops when the task is done or the iteration limit is reached.

## Usage

To start a new work session:
```
/ce:work
```

To resume a paused session, pass the session ID printed at the start of the previous run:
```
/ce:work <session-id>
```

## Steps

1. Look for a plan file in `.context/compound-engineering/plan/`. If none exists, tell the user to run `/ce:plan` first and stop.

2. Read the plan file and find the first task with `status: pending`. Extract its `description` field as `<task_description>`.

3. Determine whether an argument was passed to this command.
   - If no argument: run a new session:
     ```
     ce-work "<task_description>" "<path to plan file>"
     ```
   - If an argument was passed (the session ID): run:
     ```
     ce-work "<task_description>" "<path to plan file>" <session-id>
     ```

4. When the engine exits, report the session ID and final error state to the user.

## Constraints

- Never start a work session without a plan file present.
- Always report the session ID so the user can resume if needed.
