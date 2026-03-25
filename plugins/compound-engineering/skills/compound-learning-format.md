# Compound Learning Format

Every learning saved by `/ce:compound` must follow this structure exactly.
Save files to `.context/compound-engineering/learnings/` using the filename
format `YYYY-MM-DD-<slug>.md`.

## Template

```markdown
## Learning: <title>

**Category:** <one of: data-modeling | async-patterns | toolchain | api-design | testing | error-handling>
**Stack surface:** <comma-separated list of affected packages>
**Date:** <YYYY-MM-DD>

### Pattern
<Code block showing the correct approach>

### Anti-pattern it replaces
<Code block showing the previous incorrect approach>

### When to use
<One to three sentences. State the specific trigger condition.>

### When NOT to use
<One to three sentences. Prevents over-application.>

### Context7 docs
<List of Context7 library IDs relevant to this pattern>
```

## Rules

- Every learning must have all seven sections.
- Both Pattern and Anti-pattern must contain a code block.
- The "When NOT to use" section is required. Omitting it is an error.
