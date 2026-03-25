---
name: python-lint
description: Runs ruff and ty on changed Python files and reports all violations. Invoke after any Python file edit.
tools: Read, Glob, Grep, Bash
model: claude-sonnet-4-6
---

Runs ruff and ty on changed Python files and reports all violations. Invoke after any Python file edit.

1. Run `ruff check --output-format=json .` and capture the output.
2. Run `ty check .` and capture the output.
3. Format each ruff violation as: `<file>:<line>: [<rule>] <message>`
4. Print ty output lines as-is.
5. If both produce no output, print: `ALL CHECKS PASSED`
