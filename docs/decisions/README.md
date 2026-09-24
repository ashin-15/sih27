# Architecture decisions

Record a new ADR when a choice materially changes architecture, a public interface, persistence, security, major dependency, algorithm, model strategy, infrastructure or performance tradeoff. Do not invent past decisions. Draft options are not decisions. A user-approved product choice belongs first in the PRD decision log; its technical consequence can receive an ADR here.

Use filenames `0001-short-title.md`, increasing monotonically. Template:

```markdown
# Decision: <title>

Status: Proposed | Accepted | Superseded
Date: YYYY-MM-DD

## Context
## Problem
## Options Considered
## Decision
## Reasoning
## Consequences
## Rejected Alternatives
## Evidence
```

Link the relevant FR/AC, research question and tests. State FACT, ASSUMPTION, HYPOTHESIS, MEASURED RESULT, LITERATURE-BACKED CLAIM, DESIGN DECISION or UNKNOWN where the distinction matters. A superseded ADR stays in history and points to its replacement.
