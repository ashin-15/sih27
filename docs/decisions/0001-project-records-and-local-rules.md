# Decision: Project records and local agent rules

Status: Accepted
Date: 2026-09-24

## Context

The standalone Python package has runtime, tests, presets, run evidence, draft product specs,
current project documentation, and historical research with different handling needs. The
provided code archive demonstrated task gates, research modules, an append-only log, and local
subsystem guidance. Its product architecture and results are not adopted here.

## Problem

Future work needs discoverable current state, open items, and directory-specific behavior without
confusing proposals or historical evidence with implemented Drishti capabilities.

## Options Considered

One root manual only; duplicate full manuals in every directory; a root manual plus focused local
rules and linked project records.

## Decision

Use the root `AGENTS.md` as the shared contract. Add focused nested `AGENTS.md` files where
responsibilities differ. Keep `docs/` as the current project record, `docs/research/` for new
research, package specs as drafts until approved, and `research/sih26053/` as an archive.
Track new work in `work-log.md`, blockers in `open-items.md`, and gate status in `execution-plan.md`.

## Reasoning

Local rules are short enough to read at the point of work while the root manual retains common
invariants. Separate records make current implementation, proposals, and historical evidence
distinguishable.

## Consequences

Substantive changes update the relevant records. Agents must read the root and applicable local
instructions. Documentation maintenance is part of task completion.

## Rejected Alternatives

Copying the supplied archive's team assignments, algorithm claims, and performance figures would
misstate this package. Repeating the entire root manual in every directory would drift quickly.

## Evidence

Repository inspection on 2026-09-24; current source map in `project-assessment.md`; supplied
archive's execution, research, and subsystem documentation. This decision is about workflow only.
