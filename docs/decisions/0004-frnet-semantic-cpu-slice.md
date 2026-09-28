# Decision 0004: approved FRNet semantic CPU slice

Date: 2026-09-27. Status: Accepted for T-003 implementation, pending quality
acceptance. Product owner: "I have am approving T-003. Move forward with the
implementation." This approves the semantic-only slice in
[the T-003 proposal](../t-003-semantic-checkpoint-proposal.md), not full-release
AC-008 or later object, motion and free-space stages.

## Decision

- Use the user-supplied FRNet SemanticKITTI checkpoint for local CPU development,
  pinned to SHA-256 `09adea9005215641aea915cc3aa2bebf74582ce240cca91dedd07940ad94285e`.
  Keep checkpoint, tensor export and dataset outside source control. Do not
  redistribute the weights while their separate terms and exact public-byte
  identity are unknown.
- Pin the authors' source to commit `d3749c8bcf6ef0fe2c95adea55375ac73a4b3825`.
  Use a separate Python 3.8 CPU worker with the tested upstream dependencies,
  retaining Drishti's locked Python 3.12 runtime. Only accepted sensor-frame
  x/y/z/intensity crosses the worker boundary. Oracle labels do not.
- Preserve the approved T-002 schema-1 diagnostic result. Add a schema-2
  `stage=semantic` result for point and cell semantic evidence, model score,
  checkpoint/source/class-map provenance and timing. It explicitly leaves
  motion, instances, tracks, occupancy/free-space and temporal evidence unknown.
  The same-process product evaluator validates this result before a receipt.
- Convert FRNet channels 0..18 to Drishti learning IDs 1..19 and ignore
  channel 19 to unknown ID 0. The maximum softmax value is an uncalibrated
  model score. Official SemanticKITTI prediction files contain representative
  raw IDs, with rejected points written as raw unknown 0.
- Provide local replay and offline evaluation commands. Sequence 08 is the
  held-out validation split under the authors' SemanticKITTI configuration;
  sequence 00 is training data and never supplies the acceptance score.

## Remaining gates

D-005 has no approved numeric semantic mIoU, per-class, by-range or maximum
unknown-coverage thresholds. A single-scan official evaluator run validates
format and score calculation only. Full sequence 08 evaluation, exact weight
terms/identity and a reviewed training split/recipe remain required before
T-003 can be marked DONE. The 100 ms complete-path CUDA release gate stays
separate and NOT VERIFIED.

## Evidence

[Experiment 0024](../research/experiments/0024-t003-frnet-drishti-integration.md)
records the installed-wheel replay and exact prediction comparison.
