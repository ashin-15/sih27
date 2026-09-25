# O-001 CUDA frame-path goal

Status: CPU-first implementation on the current laptop is selected; the integrated CUDA backend is optional future support. GPU validation is deferred and must not block approved CPU-only work. The full product contract remains pending, 2026-09-25.

## Goal and evidence boundary

DESIGN DECISION: build a CUDA frame path for standalone Drishti-2.5 and test whether it can
publish each complete replay result within the selected strict 100 ms per-scan deadline, with
zero misses in the accepted window. This is an O-001 implementation direction, not an achieved
deadline or approval of the still-draft product contract.

FACT: this laptop has Intel Core Ultra 9 185H, integrated Intel Arc graphics and an NPU.
`lspci -nn` on 2026-09-25 shows no NVIDIA GPU, and `nvidia-smi` is unavailable. CUDA cannot run
on its present accelerator. The earlier first-release laptop choice is superseded for the CUDA
release gate by [decision 0002](decisions/0002-cuda-replay-release-platform.md): a specific
NVIDIA host will own the 100 ms acceptance test. This laptop remains the CPU reference.

FACT: historical vrgrid implemented a CuPy/CUDA frame path with device-resident map arrays and
measured sub-100 ms p99 on an RTX 5050 laptop. Its T4 free-running p99 exceeded 100 ms. These
are architecture references, not Drishti code or evidence for this laptop. See
`../vrgrid-26/docs/gpu-lane/08-GPU-FRAME-LOOP.md`,
`../vrgrid-26/docs/gpu-lane/13-PS-SCHEDULE.md` and
`../vrgrid-26/docs/gpu-lane/t4/timing_cuda.log`.

## Draft implementation and proof contract

FACT: `MappingEngine(device="cuda")` and CLI `--device cuda` now select a CuPy path for range
projection, cell ownership, grouping and reductions. Filtering, transforms,
Patchwork++ and snapshot construction remain on CPU. The CUDA path copies public results
back to immutable NumPy arrays; it is not a device-resident complete pipeline or a measured
speedup. Selection fails before a CLI output directory is created when CUDA is unavailable.
The current 100 ms replay diagnostic requires `--view none`, keeping Rerun outside the
deadline. Its current frame-result receipt is measured before the audit JSONL flush;
the receipt covers the implemented single-frame payload, not a frozen first-release
output. Earlier recorded-view runs remain historical diagnostics under their source
digests. CPU regression tests pass; CUDA parity, numerical edges and throughput are NOT
VERIFIED on this Intel laptop. A CPU NumPy array API check compares the CUDA algorithm's
arithmetic with the reference on 2,000 points for square/radial and geometric/oracle
combinations; it is not proof that the CuPy kernels execute or meet a deadline.

1. Keep `MappingEngine.process` as the shared CLI, evaluator and viewer execution path. Add an
   explicit backend selection with a CPU reference path; fail clearly if CUDA is selected
   without a usable NVIDIA device. Do not silently change semantic or map contracts.
2. Profile the approved complete path first. Move measured hotspots to device-resident,
   bounded buffers while preserving accepted point order, IDs, learning IDs, lattice ownership,
   point accounting and snapshot meaning. Keep CPU-only components explicit in timing.
3. Compare CPU/CUDA outputs on identical scans and configurations, including negative
   coordinates, projection ties, unknown classes, boundary density, sequence reset and
   overflow. Specify allowed numerical tolerance per field before judging parity.
4. Gate performance on the approved release machine and complete output handoff: paced
   arrivals, model and temporal stages enabled, zero missing scans, zero deadline misses,
   bounded queue/resource use, and per-scan maximum output age under 100 ms. Record CPU/GPU
   stage timings, transfers, RSS/VRAM, output age and failures. A p99 below 100 ms alone does
   not meet the zero-miss rule.

DESIGN DECISION, handoff review: the complete-product publication event is the same-process
evaluator's receipt after validation of a versioned immutable result. Persist receipts and
audit evidence; full-payload disk persistence is not part of the endpoint. First-release
output is evidence-only; planner-facing use is deferred. The existing current-slice diagnostic
does not yet implement that complete product contract.

DEFERRED: target NVIDIA host selection/access and approval of the proposed workload/window
and density cap. OPEN: complete payload schema, model and quality gates, bounded audit/failure
behavior, resource limits and explicit approval of the frozen PRD/design/acceptance contract.
The existing O-001 goal and AC-008 remain open until these are resolved and measured.
