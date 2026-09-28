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

## Dependency order after T-002

1. T-003: pin exact licensed SemanticKITTI-compatible checkpoint, class map and milestone.
2. Obtain CPU quality baselines and reviewed detector/track/motion/free-space references;
   freeze D-005 numeric gates before final held-out scoring.
3. T-004 to T-007: instances, temporal motion, ray proof, map and bounded audit in order.
4. Identify/inventory a physical NVIDIA host, pin resource limits and validate CUDA parity.
5. T-008: run the complete release protocol and judge all blocking ACs, including AC-008.
