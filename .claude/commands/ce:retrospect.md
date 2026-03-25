# /ce:retrospect

Analyze all compound learnings from the past two weeks and surface patterns.

## Steps

1. List all files in `.context/compound-engineering/learnings/` sorted by modification date, newest first.

2. Read each file modified in the last 14 days.

3. Group learnings by their `**Category:**` field value.

4. For each category with two or more learnings, report:
   - Category name
   - Number of learnings in it
   - Common theme described in one sentence

5. Find any two learnings with the same `**Stack surface:**` value but different patterns. Report each conflict with both learning file names and dates.

6. Find any learning whose `**Date:**` is more than 90 days ago. For each, ask the user: "Learning '<title>' is 90+ days old. Keep / Update / Archive?"

7. Find any ruff rule code that appears in three or more separate learnings. Report: "Rule <code> is recurring — consider adding to pre-commit config."

8. Write the full retrospect summary to: `.context/compound-engineering/retrospects/YYYY-MM-DD.md`

9. Display the summary to the user.
