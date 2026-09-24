# Project documentation rules

Read the root `AGENTS.md` first. Keep this directory as the durable, concise record of the
standalone product. Before editing a plan, check current source, tests, run evidence, and the
draft product contract. Mark FACT, ASSUMPTION, HYPOTHESIS, MEASURED RESULT, DESIGN DECISION,
or UNKNOWN where a claim could be mistaken for implemented behavior.

- Update `execution-plan.md` and `open-items.md` when scope, dependencies, status, or blockers change.
- Append to `work-log.md` after substantive work; keep completed and unresolved items visible.
- Put technical research in `research/`, interface changes in `interfaces.md`, and material
  architecture choices in `decisions/`. Link records instead of copying long source descriptions.
- Do not convert a draft product choice into an accepted decision. Preserve failed findings and
  prior status changes in the log.
- Validate links and claimed test results against the working tree before calling a task DONE.
