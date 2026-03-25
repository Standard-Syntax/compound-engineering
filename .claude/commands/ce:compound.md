# /ce:compound

Document a solved problem to compound your team's knowledge.

## What This Does

1. Captures the problem, solution, and context from the current work session.
2. Formats it using the Compound Learning Format.
3. Saves it to `.context/compound-engineering/learnings/`.
4. Offers to add it to CLAUDE.md as a project convention.

## Structured Learning Mode

After completing the standard compound steps, also do the following:

1. Check `.context/compound-engineering/context-pack.md` files from the last three sessions. If any ruff rule code (e.g., `UP007`, `E501`) appears in all three, add this note to the learning being saved:

   ```
   **Recurrence alert:** Rule <code> appeared in 3 or more recent sessions.
   Consider enabling auto-fix: add `"<code>"` to `tool.ruff.lint.fixable`
   in pyproject.toml.
   ```

2. Save the learning using the Compound Learning Format skill. The file goes in `.context/compound-engineering/learnings/YYYY-MM-DD-<slug>.md`.

3. Ask the user: "Should this learning be added to CLAUDE.md as a project convention? (yes/no)"
   If the answer is yes, open `CLAUDE.md` and append the learning under a `## Discovered Conventions` heading. Create the heading if it does not exist.
