"""LangGraph nodes for the CE work engine.

All nodes are async def. Subprocess calls use anyio.fail_after() for timeout
(anyio.run_process has NO built-in timeout parameter). The LLM client is
cached via functools.cache to preserve the connection pool across retries.
"""

import datetime
import functools
import json
import logging
from pathlib import Path
from typing import Any

import anyio
from anyio.to_thread import run_sync as to_thread_run_sync
from httpx import HTTPError as HttpxHTTPError
from langchain_anthropic import ChatAnthropic
from langgraph.types import interrupt
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ce_engine.config import settings
from ce_engine.prompts import build_work_prompt
from ce_engine.state import RuffError, SolutionSummary, WorkIntent, WorkState, make_continue_intent
from ce_engine.toolchain import (
    compute_error_delta,
    run_command,
    run_pytest,
    run_ruff_check,
    run_ty_check,
)


@functools.cache
def _get_llm() -> ChatAnthropic:
    """Cached LLM client. functools.cache makes the cached value immutable after first call."""
    return ChatAnthropic(
        model_name=settings.model_name,
        timeout=60.0,  # read timeout; connect uses httpx default
    )


def _parse_intent(response_text: str) -> WorkIntent:
    """Parse intent from LLM response by scanning backwards for JSON.

    The LLM is instructed to put a JSON intent on the final line, but it
    may include explanatory text above it. This scans backwards from the
    last line until a valid JSON object containing 'intent' is found.

    Also detects [PHASE_COMPLETE] and [COMPACT] markers in plain text.
    """
    text = response_text.strip()

    # Check for phase-compact marker first (take precedence)
    if "[PHASE_COMPLETE]" in text:
        return WorkIntent(intent="phase_complete")

    # Check for compaction marker
    if "[COMPACT]" in text:
        return WorkIntent(intent="compact")

    lines = text.split("\n")
    for i in range(len(lines) - 1, -1, -1):
        candidate = lines[i].strip()
        if not candidate:
            continue
        try:
            data = json.loads(candidate)
            if isinstance(data, dict) and "intent" in data:
                return WorkIntent(
                    intent=data.get("intent", "continue"),
                    reason=data.get("reason"),
                    options=data.get("options"),
                    operation=data.get("operation"),
                    files=data.get("files"),
                    description=data.get("description"),
                )
        except json.JSONDecodeError:
            continue
    # No valid JSON found -- default to blocked to halt and ask a human
    logging.warning("Could not parse intent from LLM response, defaulting to blocked")
    return WorkIntent(intent="blocked", reason="Could not parse LLM intent response")


async def _run_lint_checks(path: str = ".") -> tuple[list[RuffError], str]:
    """Run ruff and ty concurrently. Returns (ruff_errors, ty_output)."""
    ruff_errors: list[RuffError] = []
    ty_output: str = ""

    async def _ruff() -> None:
        nonlocal ruff_errors
        ruff_errors = await run_ruff_check(path)

    async def _ty() -> None:
        nonlocal ty_output
        ty_output = await run_ty_check(path)

    async with anyio.create_task_group() as tg:
        tg.start_soon(_ruff)
        tg.start_soon(_ty)

    return ruff_errors, ty_output


def _token_estimate(text: str) -> int:
    """Estimate token count (rough: ~4 chars per token)."""
    return len(text) // 4


def _extract_plan_metadata(plan_ref: str) -> str:
    """Extract deferred questions, scope boundaries, and phase definitions from plan file."""
    if not plan_ref:
        return ""
    plan_path = Path(plan_ref)
    if not plan_path.exists():
        return ""

    try:
        content = plan_path.read_text()
    except OSError:
        return ""

    lines = content.split("\n")
    sections: list[str] = []
    in_scope = False

    for line in lines:
        stripped = line.strip()
        # Scope boundaries
        if any(
            stripped.lower() == marker.lower()
            for marker in ["out of scope", "not doing", "excludes", "scope boundaries"]
        ):
            sections.append(f"\n## {stripped}\n")
            in_scope = True
        elif in_scope and stripped.startswith("## "):
            in_scope = False
        elif in_scope and stripped:
            sections.append(f"  {stripped}\n")

        # Deferred / unknown markers
        is_deferred = any(
            stripped.lower().startswith(marker.lower())
            for marker in ["deferred:", "unknown:", "tbd:", "implementation-time unknowns:"]
        )
        is_question = stripped.rstrip().endswith("?") and len(stripped) > 5
        if (is_deferred or is_question) and not in_scope:
            sections.append(f"\n## Deferred Question\n  {stripped}\n")

        # Phase definitions
        if stripped.startswith("## Phase ") or stripped.startswith("### Phase "):
            sections.append(f"\n## {stripped}\n")
            in_scope = False

        # Verification criteria
        if stripped.startswith("- [ ]") or stripped.startswith("* [ ]"):
            sections.append(f"  {stripped}\n")

    result = "".join(sections)
    # Truncate if over 500 tokens (~2000 chars)
    if _token_estimate(result) > 500:
        result = result[:2000]
    return result


async def prefetch_node(state: WorkState) -> dict[str, Any]:
    """Run all tools and build the Context Pack before any LLM call.

    Runs ruff and ty concurrently via _run_lint_checks for 30-50% time reduction.
    Enriches context pack with plan metadata, relevant compound doc summaries,
    and research artifact references.
    """
    ruff_errors, ty_output = await _run_lint_checks(".")

    error_count = len(ruff_errors)
    ty_status = ty_output if ty_output else "clean"
    error_delta = (
        f"{error_count} ruff errors detected.\nty: {ty_status}"
        if error_count > 0 or ty_output
        else "No errors found."
    )

    # Search docs/solutions/ using frontmatter relevance scoring, fall back to learnings_path
    def _read_learnings() -> tuple[str, list[SolutionSummary], str | None]:
        def _parse_frontmatter(path: Path) -> dict[str, Any]:
            """Parse YAML frontmatter from a markdown file without a YAML library."""
            text = path.read_text()
            if not text.startswith("---"):
                return {}
            end = text.find("\n---", 3)
            if end == -1:
                return {}
            fm_text = text[4:end]
            result: dict[str, Any] = {}
            for line in fm_text.split("\n"):
                if ":" not in line:
                    continue
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if value.startswith("[") and value.endswith("]"):
                    result[key] = [v.strip() for v in value[1:-1].split(",")]
                else:
                    result[key] = value
            return result

        def _score_doc(fm: dict[str, Any], keywords: set[str]) -> int:
            score = 0
            module = str(fm.get("module", "")).lower()
            component = str(fm.get("component", "")).lower()
            problem_type = str(fm.get("problem_type", "")).lower()
            tags: list[str] = fm.get("tags", []) or []
            date_str = str(fm.get("date", ""))

            for kw in keywords:
                kw_lower = kw.lower()
                if kw_lower in module:
                    score += 3
                if kw_lower in component:
                    score += 2
                if kw_lower in problem_type:
                    score += 1
                for tag in tags:
                    if kw_lower in tag.lower():
                        score += 2

            if date_str:
                try:
                    doc_date = datetime.date.fromisoformat(date_str[:10])
                    days_old = (datetime.date.today() - doc_date).days
                    if days_old < 30:
                        score += 1
                except (ValueError, TypeError):
                    pass

            return score

        def _read_solutions() -> tuple[list[tuple[int, str]], list[SolutionSummary]]:
            solutions_dir = settings.solutions_path
            if not solutions_dir.exists():
                return [], []
            candidates = list(solutions_dir.glob("**/*.md"))
            if not candidates:
                return [], []

            task_keywords = set()
            if state.task_description:
                task_keywords.update(
                    w.lower() for w in state.task_description.split() if len(w) > 3
                )

            scored: list[tuple[int, Path, dict[str, Any]]] = []
            for path in candidates[:50]:
                try:
                    fm = _parse_frontmatter(path)
                    score = _score_doc(fm, task_keywords)
                    if score > 0:
                        scored.append((score, path, fm))
                except (OSError, ValueError) as exc:
                    logging.debug("Failed to score doc %s: %s", path, exc)
                    continue

            scored.sort(key=lambda x: x[0], reverse=True)
            top_entries = [(score, p, fm) for score, p, fm in scored[:5]]

            results: list[tuple[int, str]] = []
            summaries: list[SolutionSummary] = []
            for score, path, fm in top_entries:
                try:
                    content = path.read_text()
                    # Extract title from first H1
                    title = ""
                    for line_text in content.split("\n")[:20]:
                        if line_text.startswith("# "):
                            title = line_text[2:].strip()
                            break
                    # Extract metadata from frontmatter (already parsed)
                    root_cause = str(fm.get("root_cause", ""))
                    module_name = str(fm.get("module", ""))
                    tags: list[str] = fm.get("tags", []) or []
                    # Extract solution text (first 100 words after frontmatter)
                    body_start = content.find("---", 3)
                    if body_start == -1:
                        body_start = 0
                    body = content[body_start:].split("\n\n", 1)[-1] if body_start > 0 else content
                    solution_words = " ".join(body.split())[:500]
                    summaries.append(
                        SolutionSummary(
                            title=title or path.stem,
                            module=module_name,
                            root_cause=root_cause,
                            solution=solution_words,
                            file_path=str(path),
                            relevance_tags=tags,
                        )
                    )
                    results.append((score, content[:1000]))
                except (OSError, ValueError) as exc:
                    logging.debug("Failed to read solution doc %s: %s", path, exc)
                    continue
            return results, summaries

        def _fallback_learnings() -> list[tuple[int, str]]:
            learnings_dir = settings.learnings_path
            if not learnings_dir.exists():
                return []
            recent = sorted(
                learnings_dir.glob("*.md"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )[:2]
            return [(0, p.read_text()[:500]) for p in recent]

        def _find_research_artifact() -> str | None:
            research_dir = Path("docs/research")
            if not research_dir.exists():
                return None
            plan_tags = set(w.lower() for w in (state.task_description or "").split() if len(w) > 4)
            for path in research_dir.glob("*.md"):
                try:
                    fm = _parse_frontmatter(path)
                    path_tags = set(str(fm.get("tags", []) or []))
                    path_topic = str(fm.get("topic", "")).lower()
                    if plan_tags & path_tags or any(t in path_topic for t in plan_tags):
                        return str(path)
                except (OSError, ValueError) as exc:
                    logging.debug("Failed to check research artifact %s: %s", path, exc)
                    continue
            return None

        solutions_results, solution_summaries = _read_solutions()
        if len(solutions_results) >= 2:
            learnings_str = "\n".join(
                f"[{score}]\n{content}" for score, content in solutions_results
            )
        else:
            fallback = _fallback_learnings()
            combined = solutions_results + fallback
            learnings_str = "\n".join(f"[{score}]\n{content}" for score, content in combined[:2])

        research_artifact = _find_research_artifact()
        return learnings_str, solution_summaries, research_artifact

    learnings_str, solution_summaries, research_artifact = await to_thread_run_sync(_read_learnings)

    # Extract plan metadata
    plan_metadata = await to_thread_run_sync(lambda: _extract_plan_metadata(state.plan_ref))

    # Get current git branch
    git_result = await run_command(
        ["git", "branch", "--show-current"], timeout=settings.git_timeout
    )
    git_branch = git_result.stdout.strip() or "unknown"

    # Get list of changed files
    diff_result = await run_command(
        ["git", "diff", "--name-only", "HEAD"], timeout=settings.git_timeout
    )
    git_diff = diff_result.stdout.strip() or "none"

    context_pack_path = settings.context_pack_path
    context_pack_path.parent.mkdir(parents=True, exist_ok=True)

    # Build context pack sections
    project_section = (
        "<project>\n"
        "  python: 3.13\n"
        "  package_manager: uv\n"
        "  linter: ruff\n"
        "  type_checker: ty\n"
        "</project>\n\n"
    )
    task_section = (
        "<current_task>\n"
        f"  branch: {git_branch}\n"
        f"  changed_files: {git_diff}\n"
        f"  task: {state.task_description}\n"
        f"  plan_ref: {state.plan_ref}\n"
        "</current_task>\n\n"
    )
    prefetch_section = (
        "<pre_fetched>\n"
        "  ruff_errors: |\n"
        f"    {json.dumps([e.model_dump() for e in ruff_errors], indent=4)}\n"
        "  ty_errors: |\n"
        f"    {ty_output}\n"
        "</pre_fetched>\n\n"
    )
    learnings_section = (
        f"<relevant_learnings>\n  {learnings_str or 'None available.'}\n</relevant_learnings>\n\n"
    )
    plan_meta_section = (
        f"<plan_metadata>\n  {plan_metadata or 'None extracted.'}\n</plan_metadata>\n\n"
    )
    solutions_section = (
        "<relevant_solutions>\n"
        + (
            "\n".join(
                f"  ## {s.title} (module: {s.module})\n"
                f"  **Root cause**: {s.root_cause}\n"
                f"  **Solution**: {s.solution[:100]}...\n"
                for s in solution_summaries[:3]
            )
            if solution_summaries
            else "  None available.\n"
        )
        + "\n</relevant_solutions>\n\n"
    )
    research_section = (
        f"<research_artifact>\n  {research_artifact or 'None found.'}\n</research_artifact>\n\n"
    )

    # Token budget enforcement: total <= 4000 tokens
    # Sections: project (~100) + task (~200) + prefetch (~500-1500) + learnings (~500-1500)
    #          + plan_metadata (~500) + solutions (~300) + research (~100) = ~2700-4500
    # Truncation priority: drop learnings first, then solutions, then plan_metadata
    all_sections = [
        project_section,
        task_section,
        prefetch_section,
        learnings_section,
        plan_meta_section,
        solutions_section,
        research_section,
    ]
    total_text = "".join(all_sections)
    total_tokens = _token_estimate(total_text)

    if total_tokens > 4000:
        # Truncate learnings first (keep 1 entry if 2+ exist)
        if len(solution_summaries) > 2:
            solution_summaries = solution_summaries[:2]
            solutions_section = (
                "<relevant_solutions>\n"
                + "\n".join(
                    f"  ## {s.title} (module: {s.module})\n"
                    f"  **Root cause**: {s.root_cause}\n"
                    f"  **Solution**: {s.solution[:100]}...\n"
                    for s in solution_summaries[:2]
                )
                + "\n</relevant_solutions>\n\n"
            )
            all_sections = [
                project_section,
                task_section,
                prefetch_section,
                learnings_section,
                plan_meta_section,
                solutions_section,
                research_section,
            ]
            total_text = "".join(all_sections)
            total_tokens = _token_estimate(total_text)

        if total_tokens > 4000:
            # Truncate learnings at line boundary (~500 chars)
            truncated_lines: list[str] = []
            chars = 0
            for line in learnings_str.split("\n"):
                if chars + len(line) > 500:
                    break
                truncated_lines.append(line)
                chars += len(line)
            truncated = "\n".join(truncated_lines)
            learnings_section = (
                "<relevant_learnings>\n"
                f"  {truncated if truncated else 'None available.'}\n"
                "</relevant_learnings>\n\n"
            )
            all_sections = [
                project_section,
                task_section,
                prefetch_section,
                learnings_section,
                plan_meta_section,
                solutions_section,
                research_section,
            ]

    context_pack_content = "".join(all_sections)

    def _write_context_pack() -> None:
        context_pack_path.write_text(context_pack_content)

    await to_thread_run_sync(_write_context_pack)

    return {
        "error_baseline": ruff_errors,
        "error_current": ruff_errors,
        "error_delta": error_delta,
        "context_pack_path": context_pack_path,
        "relevant_learnings": learnings_str,
        "relevant_solutions": solution_summaries,
        "research_artifact_path": research_artifact,
        "approved": False,
    }


async def _call_llm(prompt: str) -> str:
    """Call the LLM with exponential backoff retry (max 3 attempts)."""
    result: str | None = None
    try:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((OSError, HttpxHTTPError)),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
        ):
            with attempt:
                response = await _get_llm().ainvoke(prompt)
                result = str(response.content)
    except BaseException as exc:
        # Re-raise fatal exceptions immediately -- never swallow them.
        if isinstance(exc, (KeyboardInterrupt, SystemExit, GeneratorExit)):
            raise
        # Tenacity wraps non-retried exceptions in RetryError. Unwrap and re-raise
        # so the caller sees the true exception.
        if isinstance(exc, RetryError) and exc.last_attempt is not None:
            real_exc = exc.last_attempt.exception()
            if isinstance(real_exc, (KeyboardInterrupt, SystemExit, GeneratorExit)):
                raise real_exc from exc
        # AsyncRetrying with stop_after_attempt always yields at least once.
        # If we reach here without result, raise to avoid returning None.
        if result is None:
            msg = "AsyncRetrying loop completed without result"
            raise RuntimeError(msg) from exc
        raise RuntimeError(f"LLM call failed: {exc}") from exc
    assert result is not None, "AsyncRetrying always yields at least once"
    return result


async def llm_work_node(state: WorkState) -> dict[str, Any]:
    """Call the LLM to perform one iteration of work."""
    prompt = build_work_prompt(state)
    try:
        response_text = await _call_llm(prompt)
    except RetryError as e:
        # Persistent failure after retries -- unwrap to show the underlying exception
        last_exc = e.last_attempt.exception() if e.last_attempt else e
        error_reason = f"LLM call failed after 3 attempts: {type(last_exc).__name__}: {last_exc}"
        return {
            "llm_response": None,
            "work_intent": WorkIntent(
                intent="blocked",
                reason=error_reason,
            ),
            "iteration": state.iteration + 1,
        }

    intent = _parse_intent(response_text)

    return {
        "llm_response": response_text,
        "work_intent": intent,
        "iteration": state.iteration + 1,
    }


async def error_compact_node(state: WorkState) -> dict[str, Any]:
    """Re-run ruff, compute the delta from baseline, and update state."""
    current_errors, ty_output = await _run_lint_checks(".")

    delta = compute_error_delta(state.error_baseline, current_errors)
    ty_status = ty_output if ty_output else "clean"
    return {
        "error_current": current_errors,
        "error_delta": f"{delta}\nty: {ty_status}",
    }


async def human_interrupt_node(state: WorkState) -> dict[str, Any]:
    """Pause and ask the human to resolve a blocking question."""
    intent = state.work_intent or make_continue_intent()
    response = interrupt(
        value={
            "type": "blocked",
            "reason": intent.reason,
            "options": intent.options or [],
            "iteration": state.iteration,
        }
    )
    # Append the human's decision to the Context Pack (non-blocking)
    pack_path = Path(state.context_pack_path)

    def _append_decision() -> None:
        existing = pack_path.read_text() if pack_path.exists() else ""
        pack_path.write_text(existing + f"\n<human_decision>\n  {response}\n</human_decision>\n")

    await to_thread_run_sync(_append_decision)
    return {"work_intent": make_continue_intent()}


async def risky_op_interrupt_node(state: WorkState) -> dict[str, Any]:
    """Pause and ask the human to approve a potentially destructive operation."""
    intent = state.work_intent or make_continue_intent()
    response = interrupt(
        value={
            "type": "risky_operation",
            "operation": intent.operation,
            "files": intent.files or [],
            "message": "Approve this operation before it runs?",
            "options": ["approve", "reject"],
        }
    )
    approved = str(response).lower() in ("approve", "yes", "y", "true")
    return {"approved": approved}


async def validate_node(state: WorkState) -> dict[str, Any]:
    """Run final toolchain checks after the LLM declares the work done."""
    final_errors, ty_output = await _run_lint_checks(".")
    ty_status = ty_output if ty_output else "clean"

    pytest_result = await run_pytest(".")
    if pytest_result.returncode != 0:
        # Truncate output to avoid embedding megabytes in state
        stdout = pytest_result.stdout[:500]
        stderr = pytest_result.stderr[:200]
        suffix = "..." if len(pytest_result.stdout) > 500 or len(pytest_result.stderr) > 200 else ""
        return {
            "error_current": final_errors,
            "error_delta": (
                f"Tests failed ({pytest_result.returncode}). "
                f"Fix failing tests before continuing.\n"
                f"pytest output:\n{stdout}{suffix}\n{stderr}{suffix}"
            ),
            "work_intent": make_continue_intent(),
            "tests_passed": False,
        }

    final_delta = f"Final: {len(final_errors)} ruff errors. ty: {ty_status}"
    return {
        "error_current": final_errors,
        "error_delta": final_delta,
        "tests_passed": True,
    }


async def plan_gap_node(state: WorkState) -> dict[str, Any]:
    """Record a plan gap and ask the human whether to include it or defer."""
    intent = state.work_intent or make_continue_intent()
    gap_path = settings.plan_gaps_path
    gap_path.parent.mkdir(parents=True, exist_ok=True)

    def _write_gap() -> None:
        existing = gap_path.read_text() if gap_path.exists() else ""
        gap_path.write_text(
            existing
            + f"\n## Gap found in iteration {state.iteration}\n"
            + f"{intent.description}\n"
        )

    await to_thread_run_sync(_write_gap)

    response = interrupt(
        value={
            "type": "plan_gap",
            "description": intent.description,
            "options": ["include in this work", "defer to next plan"],
        }
    )
    if str(response).lower().startswith("include"):
        return {"work_intent": make_continue_intent()}
    # User deferred -- treat as done
    return {
        "work_intent": WorkIntent(intent="done"),
    }


async def phase_compact_node(state: WorkState) -> dict[str, Any]:
    """Handle [PHASE_COMPLETE] marker from the LLM.

    Increments the phase counter, checks for manual verification items in the plan,
    and pauses for human verification if required.
    """
    next_phase = state.current_phase + 1

    # Read the plan file to extract manual verification items for this phase
    plan_items: list[str] = []
    plan_path = Path(state.plan_ref)
    if plan_path.exists():
        plan_text = plan_path.read_text()
        # Look for "Manual Verification" section under the current phase
        # This is a simple heuristic; the plan format is markdown
        lines = plan_text.split("\n")
        in_manual_verification = False
        for line in lines:
            if "### Manual Verification" in line:
                in_manual_verification = True
                continue
            if in_manual_verification:
                if line.startswith("## ") or line.startswith("# "):
                    # Entered next top-level section
                    break
                stripped = line.strip()
                if stripped.startswith("- [ ]") or stripped.startswith("- [x]"):
                    # Extract the item text after the checkbox
                    for prefix in ("- [x] ", "- [ ] "):
                        if stripped.startswith(prefix):
                            item_text = stripped.removeprefix(prefix).strip()
                            break
                    else:
                        item_text = stripped
                    if item_text:
                        plan_items.append(item_text)

    updates: dict[str, Any] = {
        "current_phase": next_phase,
        "manual_verification_pending": False,
    }

    if plan_items:
        updates["manual_verification_pending"] = True
        updates["pending_verification_items"] = plan_items
        # Set a human-readable reason for the interrupt
        items_list = "\n".join(f"- {item}" for item in plan_items)
        updates["work_intent"] = WorkIntent(
            intent="blocked",
            reason=(
                f"Phase {next_phase} complete — manual verification required:\n{items_list}\n\n"
                "Reply when ready to proceed to the next phase."
            ),
            options=["Continue to next phase"],
        )
        return updates

    # No manual verification needed for this phase
    return updates


async def compact_progress_node(state: WorkState) -> dict[str, Any]:
    """Handle [COMPACT] marker from the LLM.

    Writes a structured progress summary to the plan file before the next iteration,
    then resets files_read_count.
    """
    plan_path = Path(state.plan_ref)

    def _write_progress() -> None:
        if not plan_path.exists():
            return

        existing = plan_path.read_text()

        progress_entry = (
            f"\n\n## Phase {state.current_phase} Progress (Iteration {state.iteration})\n"
            f"### Completed\n"
            f"- Phase work in progress (checkpoints written by LLM)\n"
            f"### Next Steps\n"
            f"- Continue Phase {state.current_phase} implementation\n"
            f"### Context Notes\n"
            f"- Files read this iteration: {state.files_read_count}\n"
            f"- LLM output contained [COMPACT] marker — progress written to plan\n"
        )

        plan_path.write_text(existing + progress_entry)

    await to_thread_run_sync(_write_progress)

    return {
        "files_read_count": 0,  # Reset after compaction
    }
