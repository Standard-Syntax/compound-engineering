@AGENTS.md

## Discovered Conventions

- **Git reset-reapply for diverged branches:** When a feature branch has diverged significantly from `main` (after multiple PRs landed) and manual conflict resolution would require re-implementing changes, prefer `git reset --hard origin/main` + re-apply the diff over attempting complex merges. Save the diff with `git diff HEAD > /tmp/fix.patch`, reset, apply, then force-push. See `.context/compound-engineering/learnings/2026-03-26-git-reset-reapply-pattern.md`.
