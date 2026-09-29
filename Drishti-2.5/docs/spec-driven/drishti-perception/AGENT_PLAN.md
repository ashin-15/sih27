# Drishti-2.5 staged agent plan

Status: T-002 approved and validated under AC-013, 2026-09-26.
Specification approval: product owner's "I approve the checklist. Move forward" after
reviewing `docs/o-001-contract-proposal.md` at commit `6af2b80`.
Plan owner: main agent. No delegated file ownership in this slice.

## Frozen shared contract

Version-1 `ProductFrameResult` and `ProductReceipt` in `src/drishti/product_result.py`,
documented in `TECH_DESIGN.md` and `docs/interfaces.md`. Any semantic change to this schema
requires a version bump and matching acceptance update; current single-frame contracts remain.

## T-002 - versioned result and evaluator

- Related requirements: FR-007/008/009; T-002 acceptance: AC-013.
- Inputs: approved O-001 proposal, existing `ScanFrame`, `FrameResult`, `MapSnapshot`,
  `MappingEngine.process`, geometric CLI and fixture replay.
- Dependencies: T-001 staged approval and CPU development choice; no model or CUDA host needed.
- Allowed source/tests: `Drishti-2.5/src/drishti/product_result.py`, `cli.py`, focused
  `Drishti-2.5/tests/` files. Allowed docs: this specification, `docs/interfaces.md`,
  `docs/decisions/`, `docs/execution-plan.md`, `docs/open-items.md`, `docs/work-log.md`.
- Forbidden: source dataset, old run artifacts, learned/temporal production behavior,
  target-hardware claims, lowered AC-008 conditions.
- Required output: sealed versioned types, canonical digest, rejecting synchronous evaluator,
  diagnostic adapter from the existing engine path, same-path CLI artifact and failure fixtures.
- Required checks: focused and full pytest with warnings as errors, Ruff lint/format,
  strict mypy, source/wheel build, installed CLI replay from a separate working directory,
  artifact inspection and `git diff --check`.
- Stop and report if a new product decision, model/checkpoint, numeric gate, live data or
  physical CUDA machine becomes necessary for T-002. Later tasks stay dependent on their own
  evidence; no subagent assignments were made.

## T-004 - bounded CPU candidate slice

- Approval: product owner, 2026-09-28, after the [three-option comparison](../../../../docs/research/experiments/0027-t004-option-comparison.md); see decision 0005.
- Related requirements/criteria: FR-002/009, AC-015. Full AC-002 and AC-008 remain separate.
- Inputs: shared `MappingEngine.process`, accepted original IDs, FRNet point semantics and ground evidence.
- Allowed: `src/drishti/obstacles.py`, `pipeline.py`, `product_result.py`, `cli.py`, focused tests and relevant docs. Forbidden: source dataset edits, model/checkpoint redistribution, tracker/free-space production claims and release-gate changes.
- Outputs: replaceable deterministic detector, sealed schema-3 candidate receipt, point-order panoptic export, source and wheel replay, fixture and held-out reports.
- Checks: focused/full pytest, Ruff, strict mypy, source/wheel build, real one-scan source/wheel parity and held-out scoring with explicit data/timing limits.
- Stop and report: no numeric AC-002 gates or independent non-panoptic obstacle annotation set exists, so the bounded implementation may pass AC-015 while full T-004 quality remains open.

## Dependency order after T-002

T-005 research and its [bounded tracking proposal](../../../../docs/t-005-tracking-proposal.md)
began 2026-09-28 after the request to start if unblocked. Production work is
approved as of 2026-09-29 under decision 0006; full AC-004/005 quality gates
remain open. The main agent owns implementation and validation.

1. T-003: pin exact licensed SemanticKITTI-compatible checkpoint, class map and milestone.
2. Obtain CPU quality baselines and reviewed detector/track/motion/free-space references;
   freeze D-005 numeric gates before final held-out scoring.
3. T-004 to T-007: instances, temporal motion, ray proof, map and bounded audit in order.
4. Identify/inventory a physical NVIDIA host, pin resource limits and validate CUDA parity.
5. T-008: run the complete release protocol and judge all blocking ACs, including AC-008.

## T-005 approved execution, 2026-09-29

Main agent owns `src/drishti/tracking.py`, `pipeline.py`, `product_result.py`, `cli.py`, `tests/test_tracking.py`, association evaluation and linked docs. No delegated work. AC-016 requires frozen fixture checks, full package gates, source/wheel multi-frame replay, offline held-out metrics and an acceptance matrix. Source data and prior artifacts stay read-only.

Result: bounded AC-016 accepted with caveats on 2026-09-29 under E-057 and
experiment 0030. Full T-005 quality/motion validation stays IN PROGRESS.
