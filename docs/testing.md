# Testing and validation

Run package commands from `Drishti-2.5/`. Use a new output directory for each run and do not alter source scans or existing run evidence.

## 2026-09-30 release host: in-process FRNet, voxels and light receipt

Environment: `uv sync --frozen --extra viz --extra cuda --extra model` (PyTorch
2.14.0+cu126, CuPy 14.2.0) on the release host of decision 0009; Smart App Control Off.
Run tests with `uv run --no-sync pytest -q -W error`, and mypy with `python -m mypy`.
Checkpoint and real-scan tests need `DRISHTI_FRNET_CHECKPOINT=../data/frnet-semantickitti_seg.pth`
and `DRISHTI_TEST_SCAN=../data/semantickitti/sequences/08/velodyne/000000.bin`.

- Full suite: 128 passed, 1 skipped (no-CUDA error path), 1 failed (pre-existing Windows
  symlink privilege). `tests/test_frnet_model.py` 9/9 including CPU/CUDA, fp16 and GPU
  interpolation agreement on scan 000000. Ruff, format and strict mypy (win32 and linux)
  pass.
- CPU torch FRNet prediction of scan 000000 has SHA-256 `66cd44a7...0b0bf4`, byte-identical
  to the authors' runtime (experiment 0024), before and after the explicit tie rule.
- Voxel grid layout self-check IoU 0.967-0.9999 on five real scans (experiment 0034).
- 2026-09-30 later: full sequence-08 GPU replay accepted; official score 0.675 (supplemental
  0.675473); false-free report 0.549% static; real CPU/CUDA parity 30/30 (experiment 0035).
- NOT VERIFIED yet: installed-wheel replay of the release pipeline, paced 100 ms learned check,
  and a clean full test run after the memory caps (non-GPU suite passed: 126 + known symlink).

## 2026-09-29 CUDA backend and learned-stage parity (RTX 4050)

Environment: `uv sync --frozen --extra viz --extra cuda` (CuPy 14.2.0 with pip
CUDA 12.9 libraries) on an RTX 4050 Laptop GPU, driver 561.00. See
[experiment 0032](research/experiments/0032-cuda-stage-parity.md).

- Full suite with CUDA: 115 passed, 1 skipped (the no-CUDA error path), 1
  failed (pre-existing Windows symlink privilege). `tests/test_cuda_backend.py`
  7/7 and `tests/test_cuda_stages.py` 5/5 ran on the GPU.
- CuPy-free environment (`--extra viz` only): 111 passed, 5 CUDA skipped, same
  symlink failure.
- Ruff lint/format, strict mypy (`python -m mypy`, win32 and `--platform linux`),
  `uv build --no-sources` and `uv lock --check` pass.
- NOT VERIFIED: real-data CPU/CUDA parity, replay timing, FRNet on GPU.

## 2026-09-29 bounded T-006 fixture and package verification (Windows)

Active workstation: Windows 11, `uv` 0.12.20, CPython 3.12.14, locked deps
(`uv sync --frozen --extra viz`; `pypatchworkpp` 1.4.1 installs as a cp312
win_amd64 wheel). Smart App Control is On: it blocked `pypatchworkpp`,
`rerun.exe` and the `mypy.exe` launcher on first use; the first two loaded on
later attempts, and mypy runs as `python -m mypy`. Results on 2026-09-29:

- `pytest -q -W error`: 105 passed, 3 CUDA skipped, 1 failed. The failure is
  pre-existing `test_output_cannot_be_written_into_the_dataset`, which needs
  symlink privilege (WinError 1314; Developer Mode or admin). Both Patchwork++
  `native` tests and the Rerun recording test pass. `tests/test_visibility.py`:
  19 passed, after correcting one expectation (unknown-ground is OCCUPIED via
  candidate support; see the contract clarification).
- Ruff lint and format check pass; strict mypy passes for 43 files with both
  the native and `--platform linux` targets; `uv build --no-sources` builds the
  sdist and a wheel containing `visibility.py`; a 3-frame synthetic demo completed.
- NOT VERIFIED: learned `--visibility` CLI replay (needs the FRNet checkpoint and
  worker), installed-wheel replay, sequence-08 replay and the SSC false-free
  report (no SemanticKITTI data or voxel labels on this workstation).

## 2026-09-29 bounded T-005 verification

The approved known-thing CPU tracking stage uses `--mode learned
--detect-obstacles --track-obstacles` with the pinned FRNet options from the
semantic workflow. [Experiment 0030](research/experiments/0030-t005-association-eval.md)
records a 200-frame saved-class association diagnostic and final real
three-scan source/installed-wheel replay. Both replay paths accepted 3/3
schema-4 receipts and emitted identical candidate/track traces and panoptic
prediction bytes. `artifacts/t005-verification-20260929.json` contains the
ignored per-run hashes and wheel provenance. The offline diagnostic observed
69 ID switches and 39 fragmentations; it is not an official 4D LSTQ result.

From `Drishti-2.5/`, `PATH="$PWD/.venv/bin:$PATH" .venv/bin/pytest -q -W error`
passed 87 tests and skipped 3 CUDA tests. Ruff check/format, strict mypy on
41 source files, and `uv build --no-sources --offline` using the populated
local uv cache passed. The initial full suite invocation without the venv
`PATH` had 82 passed, 3 skipped and one viewer test failing because its
`rerun` subprocess could not locate the executable; rerunning with the
package venv on `PATH` passed. A fresh temporary uv build cache lacked the
pinned setuptools wheel; the populated local cache completed the build.
These environment failures did not require changing tests or source behavior.


For the approved T-004 CPU candidate slice, use `--mode learned
--detect-obstacles --write-panoptic-predictions` with the pinned FRNet options
from [the semantic workflow](../Drishti-2.5/docs/frnet-semantic-workflow.md).
Source and unpacked-wheel one-scan real replays both accepted schema-3
receipts and wrote byte-identical panoptic prediction files on 2026-09-28.
[Experiment 0028](research/experiments/0028-t004-saved-prediction-eval.md)
records the complete offline sequence-08 instance baseline, timing and its
limits. The offline screen reuses saved semantic classes; it is not a
complete learned timing or AC-002/AC-008 acceptance run.
After the T-004 change, the full suite passed 77 tests with 3 CUDA skips;
Ruff lint/format, strict mypy on 38 source files, and source/wheel build
passed on 2026-09-28. The detailed table below retains dates for earlier
historical checks.

| Layer | Command or method | Verified 2026-09-24 | What it establishes | What it does not establish |
| --- | --- | --- | --- | --- |
| Install | `uv sync --frozen --extra viz` | NOT VERIFIED this session; existing environment was usable. | Locked dependency resolution when run successfully. | Runtime correctness or model availability. |
| Unit/integration | `uv run --frozen --extra viz pytest -q -W error` | 51 passed on 2026-09-25 after per-frame Rerun SDK flush instrumentation. | Present contracts, mapping, CLI and viewer fixtures pass. | Learned accuracy, real sensor performance or full requirements. |
| End to end synthetic | `uv run --frozen drishti demo --output /tmp/drishti-review-baseline-20260924 --view none --frames 3` | Completed. | CLI to engine to JSON reports works for the synthetic plane/wall. | Real-data quality, viewer lifecycle or 10 Hz guarantee. |
| Lint | `uv run --frozen ruff check .` | Passed on 2026-09-25. | Source lint. | Correct behavior. |
| Format | `uv run --frozen ruff format --check .` | Passed on 2026-09-25, 38 files already formatted. | Source formatting. | Correct behavior. |
| Types | `uv run --frozen --extra viz mypy` | Passed on 2026-09-25, 25 source files. | Static typing of `src` and `tests`. | Runtime/model behavior. |
| Build | `uv build --no-sources` | Passed again on 2026-09-25 after per-frame Rerun SDK flush instrumentation; source and wheel built. | Source/wheel artifacts. | Installed-wheel replay until exercised separately. |
| Dataset structure | `python3 scripts/verify_semantickitti.py --root <dataset> --report <new-json> --structure-only` | PASS on 2026-09-24: all 22 sequences, 43,552 scans, 23,201 labels; report in `docs/research/experiments/`. | File names, sizes, point counts and metadata. | Scan/label content integrity, annotation correctness or inference accuracy. |
| Real replay | `uv run --frozen drishti replay --dataset <dataset> --sequence <00 or 08> --mode geometric --output <new-dir> --view none --max-frames 100` | Completed twice on 2026-09-24; both 100-frame reports saved under `Drishti-2.5/runs/`. | Real dataset load and current single-frame map path; measured CPU replay latency and accounting. | Model, temporal map, viewer, live input, safety or real-time release. |
| Replay profile | Fresh 50-frame sequence 08 CLI run plus `docs/research/experiments/0002-profile-harness.py` | Completed on 2026-09-24; harness digests and accounting matched CLI on 40 frames. | Identifies sampled mapping and audit costs; see experiment 0002. | Profiler timing is not an uninstrumented deadline result or proof of optimization. |
| Durable-ingress research | C++20/SQLite, Python/SQLite, MCAP and SQLite fault harnesses in experiment 0008; two concurrent 100-frame geometric CLI replays | Seven 100-scan recorder reports reverified every payload; both concurrent CLI reports completed with 100/100 configured deadline misses; process-kill and artificial page-capacity checks passed on 2026-09-24. | Short local candidate behavior and replay contention. | Live source, power loss, physical full disk, long-run backlog, ordered scheduler or complete-path deadline. |
| Storage alternatives research | Compile `0009-storage-backends.cpp`, `0009-lmdb-faults.cpp` and `0009-lmdb-reader.cpp` with `g++ -std=c++20 -O2 -Wall -Wextra -Wpedantic -Werror`; run paced real scans on project ext4 | Three 100-scan rounds per backend and matched 1,000-scan LMDB/SQLite runs reverified all source payloads on 2026-09-25; injected LMDB kill, duplicate and map-limit checks passed. One separate-sandbox writer reopen failed `EAGAIN` with a live reader; a same-namespace held-reader check with distinct PIDs passed. A second 500-scan LMDB writer with independent reader/current replay passed, while replay missed 100/100 processing budgets. | Local storage throughput, transaction and injected-fault behavior under stated conditions. | Live sensor ack, physical disk/power fault, indefinite no-loss, stable tail latency or full-path real-time release. |
| Paced 100 ms replay check | `uv run --frozen drishti replay --dataset ../data/dataset --sequence 08 --mode geometric --output runs/drishti-o001-paced-seq08-100-20260925 --view none --max-frames 100 --check-100ms` | Completed all 100 real scans on 2026-09-25 and returned expected code 2. All 100 scheduled-arrival-to-report-flush ages missed 100 ms; frame digests, IDs, cells and accounting matched the prior baseline. See experiment 0010. | The current geometric path fails the selected per-scan deadline; exact outputs survive the timing instrumentation. | Full model/fusion/viewer path, independent capture, sustained release window or resource ceilings. |
| Packed grouping paced replay | Same command with fresh `runs/drishti-o001-packed-paced-seq08-100-20260925` output after integrating `_group_cells`. | Completed 100 scans and returned code 2. All frame digests, IDs, cells and accounting matched the first paced run. Audit-inclusive p50 fell to 193.4 ms; 100/100 output-age deadlines still missed. See experiment 0010. | Exact sampled output and local speed improvement with overflow fallback tests. | 100 ms pass, complete-path behavior, long-run and cross-configuration guarantees. |
| Packed grouping plus minimum-at projection | Same command with fresh `runs/drishti-o001-packed-scatter-paced-seq08-100-20260925` output. | Completed 100 scans and returned code 2. Every frame digest, ID, cell count and accounting record matched the packed-only run. Projection p50 fell to 15.7 ms and audit-inclusive work p50 to 177.2 ms; all deadlines still missed. See experiment 0010. | Exact sampled output and local projection speed improvement. | 100 ms pass, complete-path behavior, long-run and cross-configuration guarantees. |
| Current-path profile | `.venv/bin/python ../docs/research/experiments/0002-profile-harness.py --dataset ../data/dataset --sequence 08 --frames 40 --output ../docs/research/experiments/0011-profile-seq08-40.jsonl` | Completed on 2026-09-25 with saved timing JSONL and `cProfile` text in experiment 0011. Whole `process` p50 was 133.14 ms after two optimizations. | Ranks current geometric hotspots for further exact-output work. | A full-path deadline or uninstrumented release benchmark. |
| Ordered-ID paced replays | `uv run --frozen drishti replay --dataset ../data/dataset --sequence <08 or 00> --mode geometric --output <fresh-dir> --view none --max-frames 100 --check-100ms` | Fresh sequence 08 and 00 reports saved on 2026-09-25; both returned expected code 2. All 200 frame IDs, input/map digests, cells and accounting matched their original headless baselines. Work p50 was 149.0/138.9 ms; 200/200 deadlines missed. See experiment 0010. | Ordered-ID validation preserves sampled outputs and reduces real frame-load time. | Complete-path 100 ms pass, long-run and cross-configuration evidence. |
| Current-laptop paced replays | Same command on active source with fresh `runs/drishti-o001-current-laptop-seq{08,00}-100-20260925` outputs. | Both completed 100 scans and returned expected code 2 on 2026-09-25. All 200 frame outputs matched the original headless baselines; audited work p50 was 137.0/125.1 ms and 200/200 deadlines missed. Sidecar IDs and miss totals agreed with summaries. See experiment 0010. | Exact sampled current-path output and failure of the selected geometric deadline. | Complete-path release gate, independent capture, viewer cost or sustained window. |
| Distance and histogram paced replays | Same command on active source with fresh `runs/drishti-o001-reductions-histogram-paced-seq{08,00}-100-20260925` outputs. | Both completed 100 scans and returned expected code 2 on 2026-09-25. All 200 frame outputs matched original headless baselines; audited work p50 was 122.3/108.3 ms and 200/200 deadlines missed. A separate 50-frame sequence 00 oracle replay matched its prior output. See experiment 0010. | Exact sampled geometric and oracle output after distance and histogram changes. | Complete-path 100 ms pass, independent capture, viewer cost or sustained window. |
| Native float32 ground paced replays | Same command on active source with fresh `runs/drishti-o001-native-float32-final-seq08-100-20260925` and `runs/drishti-o001-native-float32-paced-seq00-100-20260925` outputs. | Both completed 100 scans, matched original headless frame outputs and returned expected code 2; 200/200 deadlines missed. Work p50 was 120.3/108.4 ms. A 50-frame oracle replay also matched its prior output. See experiment 0010. | Installed binding's float32 input keeps sampled geometric and oracle outputs exact. | Complete-path 100 ms pass, independent capture, viewer cost or sustained window. |
| Historical recorded-view paced replay | `uv run --frozen --extra viz drishti replay --dataset ../data/dataset --sequence 08 --mode geometric --output <fresh-dir> --view record --max-frames 100 --check-100ms` on the earlier source digest in experiment 0012. | Completed 100 scans on 2026-09-25, returned expected code 2, matched headless frame outputs, and missed 100/100 deadlines. `rerun rrd verify` passed for the 270.6 MB recording. | Earlier per-frame Rerun SDK submission cost and parseable saved recording. | Per-frame SDK flush, disk `fsync`, actual display latency or complete-path release gate. |
| Per-frame Rerun SDK flush replay | Same command on current source with fresh `runs/drishti-o001-record-flush-paced-seq08-100-20260925` output. | Completed 100 scans, returned expected code 2, matched prior map outputs, and missed 100/100 deadlines. SDK flush p50 was 10.01 ms; `rerun rrd verify` passed and decoded stats showed 100 cell/raw/semantic chunks. See experiment 0012. | Diagnostic report-age boundary includes an SDK flush for each recorded scan. | Disk `fsync`, rendered display or complete-path release gate. |
| High-density cold scan | `uv run --frozen drishti replay --dataset ../data/dataset --sequence 10 --start-frame 206 --mode geometric --output <fresh-dir> --view none --max-frames 1 --check-100ms` | The 129,392-point frame completed on 2026-09-25 and returned expected code 2; its one report age was 129.13 ms. See experiment 0010. | Current path fails the selected first-scan deadline near the proposed 130,000-point maximum. | Full-sequence, warm-state, learned/temporal or viewer performance. |
| Independent scheduled producer | `uv run --frozen python ../docs/research/experiments/0013-independent-producer-replay.py --dataset ../data/dataset --sequence 08 --frames 100 --queue-capacity 2 --output <fresh-dir>` | A 10-frame smoke and 100-frame run completed with expected exit code 2 on 2026-09-25. The full run matched all baseline frame outputs, missed 100/100 deadlines and recorded 93 queue-full events. Harness Ruff lint/format and targeted mypy passed. See experiment 0013. | A separate scheduled producer with a bounded volatile queue cannot keep the current worker within 100 ms. | Live or durable capture, full product path, long-run release behavior or independent hardware clocks. |
| Exact all-unknown evidence path | `uv run --frozen drishti replay --dataset ../data/dataset --sequence <08 or 00> --mode geometric --output <fresh-dir> --view none --max-frames 100 --check-100ms`; separate oracle 50-frame and independent-producer 100-frame runs | On 2026-09-25 all 200 paced geometric, 50 oracle and 100 separate-producer frame outputs matched their saved baselines. Sequence 08/00 audited work p50 was 110.71/100.04 ms, with 200/200 paced misses; separate producer had 89 queue-full events and 100/100 misses. Full suite: 51 passed; Ruff, mypy and build passed. See experiment 0014. | Exact sampled output and lower local mapping cost with all-unknown input. | Complete-path 100 ms pass, controlled hardware state, full sequences, viewer boundary or durable input. |
| Optimized path with Rerun SDK flush | `uv run --frozen --extra viz drishti replay --dataset ../data/dataset --sequence 08 --mode geometric --output <fresh-dir> --view record --max-frames 100 --check-100ms`; `.venv/bin/rerun rrd verify` and `rrd stats` | On 2026-09-25 the 100-frame run returned expected code 2, matched same-source headless frame outputs, and missed 100/100 deadlines. Audited work p50 was 131.34 ms, SDK flush p50 10.16 ms. The RRD verified and stats showed 100 geometry/raw/semantic cell chunks each. See experiment 0015. | Current recorded geometric path fails the selected deadline even at the per-frame SDK flush boundary. | Disk `fsync`, displayed output, complete product or approved viewer gate. |
| Immutable frame-array reuse | `uv run --frozen drishti replay --dataset ../data/dataset --sequence <08 or 00> --mode geometric --output <fresh-dir> --view none --max-frames 100 --check-100ms`; 50-frame sequence 00 oracle replay | On 2026-09-25 all 200 geometric and 50 oracle frame outputs matched saved baselines. Sequence 08/00 audited work p50 was 108.35/98.93 ms, with 100/100 and 82/100 strict misses. Focused 10 and full 51 tests, Ruff lint/format, mypy and build passed. See experiment 0016. | Reusing already immutable input arrays reduces sampled preprocessing cost without changing frame outputs. | Complete-path 100 ms pass, full sequences, controlled hardware state or selected viewer boundary. |
| O-001 output-boundary audit | Inspect current `cli.py`, `pipeline.py`, `mapping.py`, `visualization.py`, saved headless/recorded artifact keys and RRD stats | On 2026-09-25 the headless 100-frame JSONL carried IDs, digests, counts and timings but no map arrays; the RRD carried selected visual layers, not all snapshot fields. See [output-boundary audit](o-001-output-boundary-audit.md). | Current 100 ms report-flush clock is a diagnostic event rather than proof of complete machine-output publication. | Frozen output payload, consumer, handoff acknowledgement or full-path AC-008. |
| Initial CUDA backend and Rerun gate split | `uv run --frozen --extra viz pytest -q -W error`; `uv run --frozen ruff check .`; `uv run --frozen ruff format --check .`; `uv run --frozen --extra viz mypy`; `uv build --no-sources` | On 2026-09-25: 56 passed, 3 CUDA tests skipped; Ruff lint/format, mypy on 27 source files and source/wheel build passed. CLI rejects unavailable CUDA before output creation and rejects `--check-100ms` with a Rerun view. A 2,000-point NumPy array API check matched reference projection and snapshot digests for square/radial and geometric/oracle combinations after moving ownership to the device algorithm and batching reduction transfers. | Default CPU path, interface guards and algorithm arithmetic under the NumPy API remain operational; the wheel includes the optional backend. | Actual CuPy kernel execution, CPU/CUDA parity, any speedup or complete-path 100 ms success on an NVIDIA host. |
| Current-frame in-process receipt diagnostic | `uv run --frozen --extra viz pytest -q -W error`; `uv run --frozen ruff check .`; `uv run --frozen ruff format --check .`; `uv run --frozen --extra viz mypy`; `uv build --no-sources` | On 2026-09-25: 57 passed, 3 CUDA tests skipped; Ruff lint/format, mypy on 29 source files and source/wheel build passed. Paced CLI fixture saved per-frame versioned receipts and separate receipt/report ages. Consumer rejected wrong frame identity and missing point alignment. | Current single-frame in-memory result is inspected before receipt, and the checker gates receipt age rather than audit flush. Report schema version 2 distinguishes the new clock endpoint. | Frozen first-release output schema, selected product consumer, learned/temporal stages, NVIDIA timing, sustained zero-miss gate or durable output. |
| Current snapshot serialization screen | `.venv/bin/python ../docs/research/experiments/0017-snapshot-output-screen.py --dataset ../data/dataset --sequence 08 --frames 10 --output <fresh-dir>`; targeted Ruff/mypy and saved exemplar verification | Ten stored and ten deflated current snapshots round-tripped bit-exact on 2026-09-25. Median sizes were 15.64/0.765 MB; encode p50 was 13.59/261.96 ms. Two frame-0 exemplar hashes and fields were independently checked. See experiment 0017. | Straightforward persisted current-snapshot format costs and exactness on the sampled scans. | Paced output age, full future payload, full sequences, directory durability, consumer acknowledgement or AC-008. |
| T-003 FRNet semantic CPU replay | See [workflow](../Drishti-2.5/docs/frnet-semantic-workflow.md) and [experiment 0024](research/experiments/0024-t003-frnet-drishti-integration.md). | On 2026-09-27, source and installed wheel each accepted a schema-2 semantic receipt for sequence 08 scan 000000; raw-ID predictions matched byte for byte. | Label-free original-point inference, pinned provenance and result format on one real scan. | Complete sequence quality, numeric D-005 gates or CUDA/release timing. |
| T-003 full sequence 08 semantic evaluation | Saved continuation supervisor, official evaluator and range evaluator in [experiment 0025](research/experiments/0025-t003-full-sequence08.md). | On 2026-09-28, 4,071 ordered predictions matched source point counts and 4,071 semantic receipts were accepted. Official mIoU was 0.675469; labeled accuracy was 0.922835. Supplemental overall metrics agreed. | Complete held-out point-semantic baseline for this pinned checkpoint. | Continuous map state across the frame 792 restart, approved D-005 gate, checkpoint weight terms or complete-path AC-008. |
| T-003 fresh CPU semantic verification | [Experiment 0026](research/experiments/0026-t003-cpu-semantic-verification.md): focused/full checks, new three-scan learned replay and 0.2 s process-tree RSS sampling. | On 2026-09-28, 22 focused and 71 full tests passed with 3 CUDA skips; Ruff, format, mypy and source/wheel build passed. The 3/3 accepted real receipts and prediction files matched the saved full run byte for byte. Saved 4,071-scan model p50 was 7,177 ms; sampled process-tree peak RSS on the fresh short run was 2.44 GB. | Current source-path functionality, reproducibility and bounded CPU measurements. | Frozen D-005 quality pass, full-sequence memory bound, complete-product timing, CUDA or release suitability. |
| T-003 semantic evaluation | Official SemanticKITTI API on a temporary one-scan view; `python -m drishti.evaluation` for supplemental by-range report. | On 2026-09-27, official one-scan mIoU was 0.439 across 19 classes with 0.916 labeled accuracy; supplemental metrics agreed. | Prediction format and evaluator wiring on one held-out scan. | Official full-sequence score or acceptance threshold. |
| Performance/model evaluation | No complete-path benchmark exists. | NOT VERIFIED. | Future acceptance requires target hardware, full held-out data, numeric gates and saved metrics. | A short demo cannot substitute. |
| Security | No dedicated scanner/gate is tracked. | UNKNOWN. | Future review should cover dataset paths, model loading and artifact provenance. | Current tests are not a security certification. |

Use the distinction: command executes; tests pass; requirements are satisfied. These are separate claims. For a bug, reproduce as near as possible to user behavior before changing code. For modified files, run focused tests plus Ruff and mypy where applicable. Broaden validation when the changed contract or acceptance risk requires it. Preserve failures in task/evidence records.

The recorded-view paced commands above are historical experiment commands. Current
`--check-100ms` requires `--view none` so Rerun is measured in a separate run.
