# Agent Instructions

This repository primarily houses the `compound-engineering` coding-agent plugin and the Claude Code marketplace/catalog metadata used to distribute it, along with a Python LangGraph work execution engine.

`AGENTS.md` is the canonical repo instruction file. Root `CLAUDE.md` exists only as a compatibility shim for tools and conversions that still look for it.

## Quick Start

```bash
cd ce_engine
uv sync
uv run ruff check src/
uv run ty check src/
```

## Working Agreement

- **Branching:** Create a feature branch for any non-trivial change. If already on the correct branch for the task, keep using it; do not create additional branches or worktrees unless explicitly requested.
- **Safety:** Do not delete or overwrite user data. Avoid destructive commands.
- **Testing:** Run `uv run pytest` after changes that affect parsing, conversion, or output.
- **Release versioning:** Releases are prepared by release automation, not normal feature PRs. The repo has three release components (`ce_engine`, `compound-engineering`, `marketplace`). GitHub release PRs and GitHub Releases are the canonical release-notes surface for new releases; root `CHANGELOG.md` is only a pointer to that history. Use conventional titles such as `feat:` and `fix:` so release automation can classify change intent, but do not hand-bump release-owned versions or hand-author release notes in routine PRs.
- **Output Paths:** Keep OpenCode output at `opencode.json` and `.opencode/{agents,skills,plugins}`. For OpenCode, command go to `~/.config/opencode/commands/<name>.md`; `opencode.json` is deep-merged (never overwritten wholesale).
- **Scratch Space:** When authoring or editing skills and agents that need repo-local scratch space, instruct them to use `.context/` for ephemeral collaboration artifacts. Namespace compound-engineering workflow state under `.context/compound-engineering/<workflow-or-skill-name>/`, add a per-run subdirectory when concurrent runs are plausible, and clean scratch artifacts up after successful completion unless the user asked to inspect them or another agent still needs them. Durable outputs like plans, specs, learnings, and docs do not belong in `.context/`.
- **ASCII-first:** Use ASCII unless the file already contains Unicode.

## Directory Layout

```
ce_engine/        Python work execution engine (LangGraph)
plugins/          Plugin workspaces (compound-engineering)
.claude-plugin/   Claude marketplace catalog metadata
docs/             Requirements, plans, solutions, and target specs
```

## Repo Surfaces

Changes in this repo may affect one or more of these surfaces:

- `compound-engineering` under `plugins/compound-engineering/`
- the Claude marketplace catalog under `.claude-plugin/`

Do not assume a repo change is "just plugin" without checking which surface owns the affected files.

## Plugin Maintenance

When changing `plugins/compound-engineering/` content:

- Update substantive docs like `plugins/compound-engineering/README.md` when the plugin behavior, inventory, or usage changes.
- Do not hand-bump release-owned versions in plugin or marketplace manifests.
- Do not hand-add release entries to `CHANGELOG.md` or treat it as the canonical source for new releases.
Useful validation commands:

```bash
cat .claude-plugin/marketplace.json | jq .
cat plugins/compound-engineering/.claude-plugin/plugin.json | jq .
```

## Coding Conventions

- Prefer explicit mappings over implicit magic when converting between platforms.
- Keep target-specific behavior in dedicated converters/writers instead of scattering conditionals across unrelated files.
- Preserve stable output paths and merge semantics for installed targets; do not casually change generated file locations.
- When adding or changing a target, update fixtures/tests alongside implementation rather than treating docs or examples as sufficient proof.

## Commit Conventions

- Use conventional titles such as `feat: ...`, `fix: ...`, `docs: ...`, and `refactor: ...`.
- Breaking changes must be explicit with `!` or a breaking-change footer so release automation can classify them correctly.

## Agent References in Skills

When referencing agents from within skill SKILL.md files (e.g., via the `Agent` or `Task` tool), always use the **fully-qualified namespace**: `compound-engineering:<category>:<agent-name>`. Never use the short agent name alone.

Example:
- `compound-engineering:research:learnings-researcher` (correct)
- `learnings-researcher` (wrong - will fail to resolve at runtime)

This prevents resolution failures when the plugin is installed alongside other plugins that may define agents with the same short name.

## Repository Docs Convention

- **Requirements** live in `docs/brainstorms/` — requirements exploration and ideation.
- **Plans** live in `docs/plans/` — implementation plans and progress tracking.
- **Solutions** live in `docs/solutions/` — documented decisions and patterns.
- **Specs** live in `docs/specs/` — target platform format specifications.
