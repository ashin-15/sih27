# Drishti-2.5

Drishti-2.5 is a standalone, CPU-default prototype for adaptive
2.5D LiDAR mapping and bounded sequence tracking. It accepts SemanticKITTI scans or a synthetic demo,
segments ground with Patchwork++, aggregates all accepted points into
multiresolution cells, and publishes an immutable snapshot. An approved CPU
slice now runs a pinned FRNet checkpoint for point semantics in an isolated
worker. The range image is auxiliary; projection collisions do not remove
points from map aggregation. Optional CUDA projection, ownership and
reductions exist, but GPU parity and timing are not verified.

## Current capabilities and limits

| Capability | Current behavior |
| --- | --- |
| Ground and elevation | Patchwork++ and per-cell ground height, vertical span, ambiguity, observed and nonground height bounds. These are observations, not clearance or passability proof. |
| Semantics and motion | Geometric mode publishes unknown values. Learned mode predicts point semantics with a pinned FRNet CPU worker and an uncalibrated model score; held-out quality acceptance is pending. Oracle mode uses aligned SemanticKITTI labels for mapping evaluation. No learned motion estimate exists. |
| Obstacles | Learned CPU mode can optionally group accepted semantic points into frame-local obstacle candidates. Each candidate has original point support and observed bounds, with ambiguity for weak or unknown evidence. This is a measured baseline, not a validated collision volume or persistent object. |
| Time | Each map snapshot is single-frame. An optional CPU stage associates observed traffic-participant candidates across frames with sequence-local IDs. There is no temporal cell fusion, metric motion estimation or stale map policy. |
| Free space | No ray-based visibility or free-space proof is produced. Unknown space must stay unknown. |
| Performance | The CLI records processing and audited end-to-end latency, deadline misses, snapshot payload, and worker RSS. A paced replay check measures scheduled-arrival-to-current-frame in-process receipt age against 100 ms per scan, with report-flush age separate. It does not establish a full-path real-time guarantee or measure viewer memory and rendering FPS. |
| Input | Dataset replay expects poses, calibration, and ordered timestamps. Per-point timestamps and scan deskew are unavailable. No live sensor ingestion exists. |

The [current-state audit](docs/spec-driven/drishti-perception/CURRENT_STATE.md)
records the earlier geometric baseline. The [PRD](docs/spec-driven/drishti-perception/PRD.md),
[technical design](docs/spec-driven/drishti-perception/TECH_DESIGN.md), and
[acceptance contract](docs/spec-driven/drishti-perception/ACCEPTANCE.md) record
the approved T-002/T-005 bounded slices and the remaining draft release stages.

## Setup and demo

Use Python 3.12 and the checked-in uv lockfile:

```bash
uv sync --frozen --extra viz
uv run --frozen drishti demo --output /tmp/drishti-demo-001 --view none --frames 3
```

`--output` must name a new directory. `--view record` writes a Rerun `.rrd`; `--view spawn` opens the viewer and needs the `viz` extra. A synthetic demo shows software behavior only. It does not establish real-data accuracy or timing on target hardware.

`--device cpu` is the default. `--device cuda` requires an NVIDIA CUDA device and a CuPy wheel matched to the target CUDA installation. CuPy is loaded only for that option, and selection fails before creating an output directory if the device or wheel is unavailable. The target host and CuPy package are not yet locked; run the CUDA parity tests there before comparing performance.

## Dataset replay

```bash
uv run --frozen drishti replay \
  --dataset /path/to/semantic-kitti \
  --sequence 08 \
  --output /tmp/drishti-seq08-001 \
  --mode geometric \
  --view none \
  --max-frames 50
```

The dataset root must contain `sequences/<XX>/velodyne`, `times.txt`, `calib.txt`, and a pose file. `--pose-source slam` reads sequence-local poses; `--pose-source kitti-gt` reads `poses/<XX>.txt`. `--mode oracle` additionally reads point-aligned labels. Keep training, validation, and evaluation sequences separate. Do not interpret oracle output as a learned prediction.

For `--mode learned`, use the [FRNet semantic CPU workflow](docs/frnet-semantic-workflow.md).
It covers the isolated model environment, checkpoint hashes, prediction files,
the official evaluator and the supplemental range report. The model runs on
CPU and the complete held-out quality gate is still open.

Add `--detect-obstacles` to a learned CPU replay to produce schema-3
`stage=candidate` receipts. Add `--write-panoptic-predictions` to write full
input-order SemanticKITTI raw `.label` files under `panoptic/` for offline
instance scoring. The second flag requires the first. Candidate bounds cover
observed returns only; the detector alone has no track, motion, free-space or
clearance output. See [T-004 experiment 0028](../docs/research/experiments/0028-t004-saved-prediction-eval.md)
for the held-out baseline and its limits.

## Outputs

Each run writes `manifest.json`, `frames.jsonl`, and `summary.json`. A recording also writes `map.rrd`. `map_digest` supports exact replay comparison. `snapshot_array_bytes` counts array payload, while `worker_peak_rss_bytes` is the process peak. `realtime_release_gate_met` remains false because the full pipeline has not been implemented and validated.

Learned runs automatically validate a schema-2 semantic-only product result
and record its receipt. `--write-predictions` adds raw-ID `.label` files under
the new run directory. The semantic-only receipts carry no object tracks.

With `--detect-obstacles`, the result and receipt use schema 3. Frame reports
include candidate class, observed bounds, ambiguity and support count; the
sealed in-memory product result also contains original supporting point IDs.
The report is audit metadata, not a full serialized product result. The
optional panoptic export is an evaluation file, not a navigation output.
With `--track-obstacles`, the result and receipt use schema 4, and the frame
audit includes sequence track IDs, lifecycle and rejected births. These
receipts keep metric velocity and covariance unknown and make no free-space
claim.

For the current-path deadline check, add `--check-100ms` to a geometric replay. It schedules
scans at 10 Hz and writes `replay-timing.jsonl` with each scheduled arrival, load lag,
in-process result receipt age and separate frame-report flush age. Exit code 2 means at
least one receipt exceeded 100 ms. The diagnostic consumer checks identity, alignment and
the full current single-frame in-memory payload before returning its receipt. It does not
define the future complete product output. The check requires `--view none`; Rerun recording
and display are measured separately. The JSONL contains audit fields and digests, not a
complete persisted map. The check does not certify filesystem durability or the
incomplete learned or temporal pipeline. The configurable `frame_budget_ms` remains a
separate diagnostic threshold.

## Verification

```bash
uv run --frozen --extra viz pytest -q -W error
uv run --frozen ruff check .
uv run --frozen ruff format --check .
uv run --frozen --extra viz mypy
uv build --no-sources
```

## Conventions

Coordinates are local map forward/left/up metres with the initial sensor translation as origin. Semantic values use SemanticKITTI learning IDs: 0 is unknown or ignored, 1 through 19 are classes. `ScanFrame` requires increasing frame IDs and timestamps. Use one `MappingEngine` per sequence. The source dataset remains read-only.

Third-party attribution is retained in [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES).


### Bounded CPU tracking

Add `--track-obstacles` with `--detect-obstacles` to learned CPU replay to
associate observed traffic-participant candidates across frames. The run
emits schema-4 tracking receipts and per-frame lifecycle traces in
`frames.jsonl`; `--max-tracks` sets live-track capacity up to 512. First-frame
tracks are tentative; a second matching observation confirms them, and
missing confirmed tracks expire after the third missed frame. Velocity and
covariance remain unknown. See the
[approved contract](../docs/t-005-tracking-proposal.md) and
[validation record](../docs/research/experiments/0030-t005-association-eval.md).
