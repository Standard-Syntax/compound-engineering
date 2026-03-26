"""Shared subprocess runners for the CE work engine.

All subprocess calls use anyio.fail_after() for timeout -- anyio.run_process()
has NO built-in timeout parameter.
"""

import json
from dataclasses import dataclass

import anyio

from ce_engine.config import settings
from ce_engine.state import RuffError


@dataclass(slots=True)
class CommandResult:
    """Result of a subprocess command execution."""

    returncode: int
    stdout: str
    stderr: str


async def run_command(cmd: list[str], *, timeout: float = 30.0) -> CommandResult:
    """Run a command with timeout via anyio.fail_after cancel scope.

    Args:
        cmd: Command and arguments as a list.
        timeout: Timeout in seconds.

    Returns:
        CommandResult with returncode, stdout, and stderr.
    """
    try:
        with anyio.fail_after(timeout):
            result = await anyio.run_process(cmd)
            return CommandResult(
                returncode=result.returncode,
                stdout=result.stdout.decode(),
                stderr=result.stderr.decode(),
            )
    # Use BaseException to catch ExceptionGroup-wrapped TimeoutError from
    # anyio's cancel scope. Never silently swallow fatal exceptions.
    except BaseException as exc:
        cancelled = anyio.get_cancelled_exc_class()
        if isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit, cancelled)):
            raise  # Never silently swallow fatal exceptions
        return CommandResult(returncode=124, stdout="", stderr="Command timed out")


async def run_ruff_check(path: str = ".") -> list[RuffError]:
    """Run ruff check and return parsed errors.

    Args:
        path: Path to check (default ".").

    Returns:
        List of RuffError objects (may be empty).
    """
    result = await run_command(
        ["ruff", "check", "--output-format=json", "--", path],
        timeout=settings.lint_timeout,
    )
    if not result.stdout.strip():
        return []
    try:
        data = json.loads(result.stdout)
        return [RuffError.model_validate(err) for err in data]
    except json.JSONDecodeError:
        return []


async def run_ty_check(path: str = ".") -> str:
    """Run ty type checker and return trimmed output.

    Args:
        path: Path to check (default ".").

    Returns:
        Trimmed stdout/stderr output or empty string if clean.
    """
    result = await run_command(
        ["ty", "check", "--", path],
        timeout=settings.lint_timeout,
    )
    if result.returncode == 0:
        return ""
    output = result.stdout + result.stderr
    return output.strip()


async def run_pytest(path: str = ".") -> CommandResult:
    """Run pytest and return the full result.

    Args:
        path: Path to test (default ".").

    Returns:
        CommandResult with pytest output.
    """
    return await run_command(
        ["uv", "run", "pytest", "--tb=short", "-q", "--", path],
        timeout=settings.pytest_timeout,
    )


def compute_error_delta(baseline: list[RuffError], current: list[RuffError]) -> str:
    """Compute human-readable delta between baseline and current ruff errors.

    Args:
        baseline: Baseline error list.
        current: Current error list.

    Returns:
        A delta description string.
    """
    baseline_keys = {(e.file, e.line, e.code) for e in baseline}
    current_keys = {(e.file, e.line, e.code) for e in current}
    resolved = baseline_keys - current_keys
    introduced = current_keys - baseline_keys
    return (
        f"{len(resolved)} errors resolved, {len(introduced)} new errors introduced. "
        f"{len(current)} total remaining."
    )
