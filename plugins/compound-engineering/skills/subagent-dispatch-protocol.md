# Subagent Dispatch Protocol

Every agent in this plugin follows these rules without exception.

## Before Starting Work

1. Read `.context/compound-engineering/context-pack.md` in full.
2. Do not run `ruff check`, `ty check`, or `git status` yourself.
   These results are already in the Context Pack.
3. Read the `<current_task>` block to understand your scope.

## During Work

4. Stay within your declared scope. If you discover work outside your scope,
   write it to `.context/compound-engineering/out-of-scope.md` and stop.
5. Write all findings and outputs to your declared output file under
   `.context/compound-engineering/`. Do not print results to the conversation.
6. Use the budget declared in your invocation prompt. Default: 10 tool calls.
   When you reach 8, finish your current action and stop.

## Output Contract

7. Every agent produces one output file at a declared path.
8. The output file must use this finding format when reporting code issues:

   ```
   FILE: <path>
   LINE: <number>
   ISSUE: <what was found>
   FIX: <exact replacement>
   ```

9. The last line of every output file must be one of:
   - `STATUS: COMPLETE`
   - `STATUS: INCOMPLETE — <reason>`

## Agent Reference Format

When referencing an agent from a skill or command, always use the
fully-qualified namespace:

```
compound-engineering:<category>:<agent-name>
```

Examples:
- `compound-engineering:review:python-modern-reviewer`
- `compound-engineering:review:pydantic-v2-validator`
- `compound-engineering:workflow:python-lint`
