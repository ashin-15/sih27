# Experiment 0052: FRNet coordinate grouping and repeatability

Date: 2026-10-22. RQ-004 / R-SYSTEM, T-003/T-008. Development optimization;
no checkpoint, weights, precision, interpolation or quality threshold change.

## Hypothesis and contract

The current model groups clamped `(batch, row, column)` coordinates six times
per inference using `torch.unique(..., dim=0)`. With row < 64 and column < 512,
`(batch * 64 + row) * 512 + column` is injective and preserves lexicographic
order. Scalar unique followed by inverse packing must therefore reproduce the
same coordinates and inverse indices. Exhaustive two-batch lattices with
duplicates, empty/singleton inputs and strides 1/2/4/8 matched on CPU and CUDA.

The [official PyTorch unique documentation](https://docs.pytorch.org/docs/stable/generated/torch.unique.html)
defines sorted unique values/rows and inverse indices. This motivates the
screen; it does not promise a speedup. Local measurements, not documentation,
decide which implementation is retained.

## Measurements

Same RTX 4050/driver/checkpoint as [experiment 0051](0051-exact-path-screen.md).
`artifacts/frnet-repeatability-20261022/` repeats each of the first three real
scans in reference/current/current/reference order within the same loaded
model. GPU inference times varied roughly 180-290 ms after initial cold work,
with no consistent improvement. Every compared semantic label and unknown
reason matched on these scans.

MEASURED RESULT: reference GPU inference itself is not confidence-byte
repeatable. Its repeat comparison differed on 41,981-47,135 points per scan,
with maximum confidence delta 0.000014842. Cross-implementation differences
were of similar scale (maximum 0.000014365). This diagnoses the failed strict
confidence comparison in `artifacts/performance-20261022-abba/parity/`; it
does not relax exact-output rules or establish new model acceptance criteria.
The four six-frame runs before that failure accepted all 24 receipts and
matched reported map/instance/track/visibility/temporal evidence, but again
missed every publication budget. The failed screen's source is preserved
beside its reports.

The CPU screen in `artifacts/frnet-repeatability-cpu-20261022/` used the first
real scan and the same loaded model. Reference inference took 4,406.48 ms cold
and 4,209.33 ms on its repeat; scalar-key inference took 3,104.35 and
3,086.21 ms. All labels, confidence values and unknown reasons matched exactly
across all four calls. This is a one-scan CPU result, not a sustained guarantee.

## Decision and validation

Retain scalar-key grouping **only on CPU**, with the internal clamped lattice
precondition documented and exact coordinates/inverse tests. Keep CUDA's
original row-grouping operation because its candidate showed no consistent
inference improvement. The GPU prototype remains in the research harness,
not the runtime. CPU grouping does not alter parameter names or checkpoint
loading; no accuracy tradeoff or retraining is introduced.

From `Drishti-2.5/`, reproduce into new directories:

```text
.venv/Scripts/python.exe ../docs/research/experiments/0052-frnet-repeatability-screen.py <new-gpu-output>
.venv/Scripts/python.exe ../docs/research/experiments/0052-frnet-repeatability-screen.py <new-cpu-output> --device cpu --frames 1
```

The harness performs lattice parity first, then patches only the grouping
helper during diagnostic inference and restores it afterward. It reports
repeat and cross-implementation differences without declaring an exact GPU
confidence pass. No evidence here meets the full 100 ms deadline or closes
T-003 quality/provenance gates.
