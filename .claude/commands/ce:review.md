# /ce:review

Run a parallel multi-agent code review on all changed files.

## What This Does

1. Builds a Context Pack for the current branch.
2. Classifies changed files by type.
3. Dispatches the appropriate review agents based on which file types are present.
4. Synthesizes all findings into one summary.

## Steps

1. Run `git diff --name-only main` and collect the list of changed files.

2. Build the Context Pack. Read the Context Pack Builder skill for the exact procedure. Write the result to `.context/compound-engineering/context-pack.md`.

3. Classify the changed files. For each file, record which categories apply:
   - **model files**: matches `**/models.py` or `**/schemas.py`, or contains the text `from pydantic import`
   - **async files**: contains the text `async def`
   - **toolchain files**: named `pyproject.toml`, `uv.lock`, or ends in `.toml`
   - **agent files**: contains `from langgraph` or `from pydantic_ai`
   - **general python files**: all remaining `.py` files not already classified

4. For each non-empty category, dispatch the matching agent. Run all dispatched agents at the same time (in parallel). Each agent writes its output to the path shown:

   | Category | Agent | Output path |
   |---|---|---|
   | model files | `compound-engineering:review:pydantic-v2-validator` | `.context/compound-engineering/review/pydantic.md` |
   | async files | `compound-engineering:review:async-patterns-reviewer` | `.context/compound-engineering/review/async.md` |
   | toolchain files | `compound-engineering:review:toolchain-conformance-checker` | `.context/compound-engineering/review/toolchain.md` |
   | agent files | `compound-engineering:review:ai-agent-reviewer` | `.context/compound-engineering/review/agents.md` |
   | general python | `compound-engineering:review:python-modern-reviewer` | `.context/compound-engineering/review/modern.md` |
   | all files | `compound-engineering:review:kieran-python-reviewer` | `.context/compound-engineering/review/full.md` |

> **Note:** Do not dispatch `compound-engineering:workflow:python-lint` — that agent was deleted in Phase 1.

5. After all agents complete, read each output file that exists and produce a summary containing:
   - Total finding count grouped by category
   - All findings marked CRITICAL (must fix before merging)
   - All findings marked WARNING (should fix)
   - Files with no findings

6. Write the summary to `.context/compound-engineering/review/summary.md` and display it to the user.
