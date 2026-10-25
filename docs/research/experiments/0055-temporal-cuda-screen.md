# 0055: bounded CUDA temporal neighbours

2026-10-22; RQ-004, T-008/T-017, O-006. Implements the first W2 slice of the
[feature-preserving workflow](../../sub100ms-workflow.md).

DESIGN DECISION: use a fused four-neighbour CUDA kernel for CUDA temporal maps.
Preserve CPU double-precision differences, neighbour order, variance threshold,
absolute-key checks across toroidal seams, and NumPy maximum behavior. Fusion,
ownership, expiry and immutable publication remain on CPU. No terrain thresholds,
model defaults, visibility rules or receipt schemas change.

The sequence-owned workspace contains 48 bytes per maximum-level slot:
12,144,432 device bytes for the default configuration. It is reused across three
levels. This excludes compiler/pool/runtime overhead; host temporal storage is
still 53,737,911 bytes. Transfers and collection are synchronous and timed.

MEASURED RESULT: `0055-temporal-cuda-screen.py`, run from the package environment
on the RTX 4050 under uncontrolled battery power, populates all 162409/253009/
162409 slots, alternates CPU/GPU order for 21 iterations and excludes first
iteration timing. All rise/drop output bytes matched. Three-level warm median:
CPU **179.63765 ms**, CUDA **11.28595 ms**, including transfer/collection.
This is an isolated dense synthetic screen, not real replay or a 100 ms result.

Fixture verification: 15 temporal tests passed, including actual CUDA sequential
full-view byte equality under motion, expiry, free evidence, unknown semantics,
slot reuse, negative coordinates and variance rejection. GPU workspace size
stays constant and published arrays remain immutable. Initial sandbox run
failed on compiler temporary-directory permissions; permitted rerun passed.

CLI selects the neighbour backend from `--device` when `--temporal` is enabled.
Manifest records `neighbour_backend` and `device_workspace_bytes`; existing
`allocated_bytes` retains its host-array meaning. Python defaults remain CPU.
The same-state real replay harness `0056-temporal-real-parity.py` compares every
fused array and summary with CPU and returns the GPU view; its duplicate work
makes its timing unsuitable for performance claims.

Full GPU fusion, real controlled tails, complete fused receipts and the total
under-100 ms requirement remain NOT VERIFIED.

## Real integration and checks

MEASURED RESULT: `0056-temporal-real-parity.py` with sequence 08, first six
scans, pinned checkpoint from 0054, learned CUDA/torch FP32, detection, tracking,
visibility, temporal, evaluator, audit-every 100, view none and check-100ms:
all six full fused views matched CPU byte for byte. Saved reports:
`artifacts/temporal-cuda-parity-20261022/`. Six receipts accepted; six late.
Instrumented timing is excluded from performance claims.

A separate normal CLI invocation with identical options (no wrapper), saved in
`artifacts/temporal-cuda-replay-20261022/`, accepted six receipts and missed six
deadlines. Five warm scans: load-through-receipt p50 **1329.3666 ms**;
temporal p50 **277.3527 ms**; processing p50 **1082.3841 ms**.
Uncontrolled power/short workload; not a controlled before/after improvement.
Release flag false. Manifest confirms CUDA neighbours and 12,144,432 device bytes.

Verification: full suite produced 182 passed, four skipped and two viewer
failures because the direct Python invocation omitted Rerun's directory from
PATH. All four viewer tests passed on rerun with `.venv/Scripts` on PATH:
combined coverage 184 passed, four skipped. Ruff check/format, strict mypy
(52 files), source/wheel build and diff whitespace checks passed. Build needed
permission to access the external uv cache. Installed-wheel replay of this new
slice remains NOT VERIFIED.
