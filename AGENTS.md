# SIH / Drishti-2.5 agent operating manual

This is the primary project contract. Read it, then the narrower `Drishti-2.5/AGENTS.md` before editing that package. Treat `docs/` as durable project context. The current product-feature specification under `Drishti-2.5/docs/spec-driven/drishti-perception/` is a draft and does not authorize implementation.

At the start of substantive work, read `docs/README.md`, `docs/open-items.md`, and the relevant
part of `docs/execution-plan.md`. Read every applicable nested `AGENTS.md` from the target path.
Afterward, update the task status, open-item register, and dated work log with actual evidence.

## Project identity

FACT: `SIH26053.md` describes an adaptive 2.5D LiDAR perception challenge. `Drishti-2.5/` is the standalone Python package. It currently maps individual scans, extracts ground, aggregates multiresolution cells, replays SemanticKITTI data and renders optional Rerun views. It is a prototype for developers and evaluators. Learned perception, detection, tracking, temporal fusion, motion estimation, free-space proof and a verified real-time guarantee are absent from the active path. See `docs/project-assessment.md`.

## Repository map

| Path | Purpose and boundary |
| --- | --- |
| `Drishti-2.5/src/drishti/` | Runtime package. `cli.py` is the command entry point; `pipeline.py` is the shared execution path; `contracts.py` and `mapping.py` own frame and snapshot contracts. |
| `Drishti-2.5/tests/` | Unit and small integration tests, including native Patchwork++ and optional viewer tests. |
| `Drishti-2.5/configs/` | Mapping configuration examples; `pyproject.toml` and `uv.lock` own package and locked dependencies. |
| `Drishti-2.5/runs/` | Saved run reports. Treat existing files as evidence and do not overwrite or clean them casually. |
| `docs/` | Current project context, assessment, task board, interfaces, validation, decisions and research workflow. |
| `research/sih26053/` | Historical research and evidence. Check provenance before using findings as current Drishti results. |
| `scripts/` and `configs/` | Repository-level dataset validation helper and optional local path convenience. |
| `SIH26053.md` | External problem statement, not proof that its requested capabilities are implemented. |

Local rules exist in `docs/`, `docs/research/`, `Drishti-2.5/src/drishti/`, `tests/`,
`configs/`, `runs/`, `Drishti-2.5/docs/`, `research/sih26053/`, and `scripts/`.

Ignored local `data/`, `artifacts/`, environments and model files are not source. Do not modify the source dataset. No database or external service is part of the current runtime. CI, deployment, live sensor input and security review procedures are UNKNOWN from this repository.

## Existing architecture

`DatasetSource.frames` or `synthetic_frames` yields `ScanFrame` -> `MappingEngine.process` validates/filter/transforms -> Patchwork++ segments ground -> `project` creates an auxiliary range image -> `aggregate_cells` creates a single-frame immutable `MapSnapshot` -> CLI writes manifest/JSONL/summary and optional `RerunView` publishes a view. Oracle annotations are evaluation input only. No persistent map service or database exists.

## Development commands

Run from `Drishti-2.5/`. Verified on 2026-09-24: `uv run --frozen --extra viz pytest -q -W error` (42 passed) and `uv run --frozen drishti demo --output /tmp/drishti-review-baseline-20260924 --view none --frames 3` (completed). Commands declared by package instructions, with their latest verification state, are in `docs/testing.md`. Use a new output directory for each demo/replay. Benchmark and deployment commands for the complete future pipeline are UNKNOWN.

## Coding conventions and invariants

- Python 3.12, typed NumPy arrays, strict mypy, Ruff E/F/I/UP/B, 100-character line length. Keep errors explicit with `ValueError` for invalid contracts and `OSError`/runtime failures at CLI boundaries.
- Preserve `ScanFrame` point alignment, unique nonnegative int64 IDs, monotonically increasing frame IDs/timestamps, declared pose/calibration convention and immutable input/output arrays.
- Preserve SemanticKITTI learning IDs: 0 unknown/ignored, 1 through 19 classes. Never turn unknown into car. Geometric production mode must not read oracle annotations.
- Mapping uses all accepted spatial points, including projection losers. Preserve accounting conservation and nonoverlapping multiresolution cell ownership.
- Ground variance is descriptive, not uncertainty. Height envelopes are not solid occupancy, clearance, passability or free-space evidence. Snapshot byte count is not process memory.
- One engine owns one sequence. Patchwork++ state is sequence-specific. Do not claim 100 ms real-time behavior from a configured budget or a short synthetic run.
- Read `docs/interfaces.md` before changing data contracts; record material decisions in `docs/decisions/`.

## Forbidden agent behavior

Do not fabricate research, citations, benchmark results, test outcomes or implementation status. Do not remove failing tests, silently change requirements or important interfaces, expose secrets or commit credentials, delete data unnecessarily, perform destructive migrations without explicit justification, replace real behavior with mocks and call it complete, or hide uncertainty. Use FACT, ASSUMPTION, HYPOTHESIS, MEASURED RESULT, LITERATURE-BACKED CLAIM, DESIGN DECISION and UNKNOWN explicitly when status matters. Mark unavailable validation NOT VERIFIED.

## Task lifecycle and definition of done

For substantive work: read applicable instructions and context; inspect the existing path and utilities; identify requirements and unknowns; research primary sources when needed; record a concise plan; make the smallest coherent change; run focused then broader checks; inspect outputs; update interfaces, ADR, research and task records when affected; report changes, evidence, limitations and risks. For bugs, reproduce end to end as a user would where possible before fixing. Do not bypass lint, type or test failures in modified files; repair nearby defects unless they demand a separate architectural task.

A task is done only when its requirement, implementation, tests, validation, documentation and evidence agree. Existing tests passing proves the current slice executes, not that the SIH problem statement is satisfied. Significant product work follows the draft PRD, technical design and acceptance process and starts only after explicit approval of a frozen contract.

## Git workflow

FACT: The checked branch is `main`; no tracked CI or review policy was found in this audit. Branch/release policy is UNKNOWN. Inspect `git status` before edits, preserve user changes, use focused commits when requested, and never rewrite history without explicit instruction. Commit messages must not add an agent co-author. Never commit secrets or model/data artifacts.
