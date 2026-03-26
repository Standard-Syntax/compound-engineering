# Compounding Engineering Plugin

AI-powered development tools that get smarter with every use. Make each unit of engineering work easier than the last.

## Components

| Component | Count |
|-----------|-------|
| Agents | 29 |
| Skills | 73 |
| MCP Servers | 1 |

## Agents

Agents are organized into categories for easier discovery.

### Review

| Agent | Description |
|-------|-------------|
| `agent-native-reviewer` | Verify features are agent-native (action + context parity) |
| `architecture-strategist` | Analyze architectural decisions and compliance |
| `ai-agent-reviewer` | Reviews LangGraph and PydanticAI agent code for correctness |
| `async-patterns-reviewer` | Reviews async Python code for structured concurrency correctness |
| `code-simplicity-reviewer` | Final pass for simplicity and minimalism |
| `data-integrity-guardian` | Database migrations and data integrity |
| `data-migration-expert` | Validate ID mappings match production, check for swapped values |
| `deployment-verification-agent` | Create Go/No-Go deployment checklists for risky data changes |
| `kieran-python-reviewer` | Python code review enforcing Python 3.13+ stack conventions |
| `migration-drift-detector` | Detect unrelated Alembic or Django migration file changes in PRs |
| `pattern-recognition-specialist` | Analyze code for patterns and anti-patterns |
| `performance-oracle` | Performance analysis and optimization |
| `pydantic-v2-validator` | Validates that all Pydantic models use the v2 API |
| `python-modern-reviewer` | Flags Python syntax that predates Python 3.13 |
| `security-sentinel` | Security audits and vulnerability assessments |
| `toolchain-conformance-checker` | Verifies project infrastructure matches the required Python toolchain |

### Research

| Agent | Description |
|-------|-------------|
| `best-practices-researcher` | Gather external best practices and examples |
| `framework-docs-researcher` | Research framework documentation and best practices |
| `git-history-analyzer` | Analyze git history and code evolution |
| `issue-intelligence-analyst` | Analyze GitHub issues to surface recurring themes and pain patterns |
| `learnings-researcher` | Search institutional learnings for relevant past solutions |
| `repo-research-analyst` | Research repository structure and conventions |

### Design

| Agent | Description |
|-------|-------------|
| `design-implementation-reviewer` | Verify UI implementations match Figma designs |
| `design-iterator` | Iteratively refine UI through systematic design iterations |
| `figma-design-sync` | Synchronize web implementations with Figma designs |

### Workflow

| Agent | Description |
|-------|-------------|
| `bug-reproduction-validator` | Systematically reproduce and validate bug reports |
| `pr-comment-resolver` | Address PR comments and implement fixes |
| `python-lint` | Runs ruff and ty on changed Python files and reports violations |
| `spec-flow-analyzer` | Analyze user flows and identify gaps in specifications |

## Commands

### Workflow Commands

Core workflow commands use `ce:` prefix to unambiguously identify them as compound-engineering commands:

| Command | Description |
|---------|-------------|
| `/ce:ideate` | Discover high-impact project improvements through divergent ideation and adversarial filtering |
| `/ce:brainstorm` | Explore requirements and approaches before planning |
| `/ce:research` | Conduct standalone codebase research producing a reusable artifact |
| `/ce:plan` | Create implementation plans |
| `/ce:review` | Run comprehensive code reviews |
| `/ce:work` | Execute work items systematically |
| `/ce:compound` | Document solved problems to compound team knowledge |
| `/ce:compound-refresh` | Refresh stale or drifting learnings and decide whether to keep, update, replace, or archive them |
| `/ce:scaffold` | Generate a new Python 3.13 project skeleton |
| `/ce:retrospect` | Analyze learnings from the past two weeks and surface patterns |
| `/ce:calibrate` | Record estimation accuracy for iteration planning |

### Utility Commands

| Command | Description |
|---------|-------------|
| `/lfg` | Full autonomous engineering workflow |
| `/slfg` | Full autonomous workflow with swarm mode for parallel execution |
| `/deepen-plan` | Stress-test plans and deepen weak sections with targeted research |
| `/changelog` | Create engaging changelogs for recent merges |
| `/ce:compact` | Produce a structured compaction summary for resuming in a new context window |
| `/generate_command` | Generate new slash commands |
| `/sync` | Sync Claude Code config across machines |
| `/report-bug-ce` | Report a bug in the compound-engineering plugin |
| `/reproduce-bug` | Reproduce bugs using logs and console |
| `/resolve-pr-parallel` | Resolve PR comments in parallel |
| `/resolve-todo-parallel` | Resolve todos in parallel |
| `/triage` | Triage and prioritize issues |
| `/test-browser` | Run browser tests on PR-affected pages |
| `/feature-video` | Record video walkthroughs and add to PR description |

## Skills

### Architecture & Design

| Skill | Description |
|-------|-------------|
| `agent-native-architecture` | Build AI agents using prompt-native architecture |

### Development Tools

| Skill | Description |
|-------|-------------|
| `compound-docs` | Capture solved problems as categorized documentation |
| `frontend-design` | Create production-grade frontend interfaces |


### Content & Workflow

| Skill | Description |
|-------|-------------|
| `document-review` | Improve documents through structured self-review |
| `file-todos` | File-based todo tracking system |
| `git-worktree` | Manage Git worktrees for parallel development |
| `claude-permissions-optimizer` | Optimize Claude Code permissions from session history |
| `resolve-pr-parallel` | Resolve PR review comments in parallel |
| `setup` | Configure which review agents run for your project |
| `scaffold` | Generate a new Python 3.13 project skeleton |
| `retrospect` | Analyze learnings from the past two weeks and surface patterns |
| `calibrate` | Record estimation accuracy for iteration planning |

### Multi-Agent Orchestration

| Skill | Description |
|-------|-------------|
| `orchestrating-swarms` | Comprehensive guide to multi-agent swarm orchestration |

### File Transfer

| Skill | Description |
|-------|-------------|
| `rclone` | Upload files to S3, Cloudflare R2, Backblaze B2, and cloud storage |

### Browser Automation

| Skill | Description |
|-------|-------------|
| `agent-browser` | CLI-based browser automation using Vercel's agent-browser |

### Beta Skills

Experimental versions of core workflow skills. These are being tested before replacing their stable counterparts. They work standalone but are not yet wired into the automated `lfg`/`slfg` orchestration.

| Skill | Description | Replaces |
|-------|-------------|----------|
| `ce:plan-beta` | Decision-first planning focused on boundaries, sequencing, and verification | `ce:plan` |
| `ce:research-beta` | Standalone research producing a compacted, reusable artifact | `ce:research` |
| `deepen-plan-beta` | Selective stress-test that targets weak sections with research | `deepen-plan` |

To test: invoke `/ce:plan-beta` or `/deepen-plan-beta` directly. Plans produced by the beta skills are compatible with `/ce:work`.

## MCP Servers

| Server | Description |
|--------|-------------|
| `context7` | Framework documentation lookup via Context7 |

### Context7

**Tools provided:**
- `resolve-library-id` - Find library ID for a framework/package
- `get-library-docs` - Get documentation for a specific library

Supports 100+ frameworks including Rails, React, Next.js, Vue, Django, Laravel, and more.

MCP servers start automatically when the plugin is enabled.

**Authentication:** To avoid anonymous rate limits, set the `CONTEXT7_API_KEY` environment variable with your Context7 API key. The plugin passes this automatically via the `x-api-key` header. Without it, requests go unauthenticated and will quickly hit the anonymous quota limit.

## Browser Automation

This plugin uses **agent-browser CLI** for browser automation tasks. Install it globally:

```bash
npm install -g agent-browser
agent-browser install  # Downloads Chromium
```

The `agent-browser` skill provides comprehensive documentation on usage.

## Installation

```
/plugin marketplace add Standard-Syntax/compound-engineering
/plugin install compound-engineering
```

For local development, add this alias to your shell profile:

```bash
alias claude-dev-ce='claude --plugin-dir ~/path/to/compound-engineering/plugins/compound-engineering'
```

Then run `claude-dev-ce` instead of `claude` to test your changes.

## Known Issues

### MCP Servers Not Auto-Loading

**Issue:** The bundled Context7 MCP server may not load automatically when the plugin is installed.

**Workaround:** Manually add it to your project's `.claude/settings.json`:

```json
{
  "mcpServers": {
    "context7": {
      "type": "http",
      "url": "https://mcp.context7.com/mcp",
      "headers": {
        "x-api-key": "${CONTEXT7_API_KEY:-}"
      }
    }
  }
}
```

Set `CONTEXT7_API_KEY` in your environment to authenticate. Or add it globally in `~/.claude/settings.json` for all projects.

## Version History

See the repo root [CHANGELOG.md](../../CHANGELOG.md) for canonical release history.

## License

MIT
