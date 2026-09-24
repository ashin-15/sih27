# Drishti-2.5

Drishti-2.5 is a standalone, CPU-first prototype for single-frame adaptive 2.5D LiDAR mapping. It accepts SemanticKITTI scans or a synthetic demo, segments ground with Patchwork++, aggregates all accepted points into multiresolution cells, and publishes an immutable snapshot. The range image is auxiliary; projection collisions do not remove points from map aggregation.

## Current capabilities and limits

| Capability | Current behavior |
| --- | --- |
| Ground and elevation | Patchwork++ and per-cell ground height, vertical span, ambiguity, observed and nonground height bounds. These are observations, not clearance or passability proof. |
| Semantics and motion | Geometric mode publishes unknown values. Oracle mode uses aligned SemanticKITTI labels for mapping evaluation; it is not autonomous inference. |
| Obstacles | Nonground return envelopes are stored per cell. There is no object detector, object boundary, class prediction, collision volume, or persistence. |
| Time | Each output is a new single-frame snapshot. There is no temporal fusion, tracking, motion estimation, or stale evidence policy. |
| Free space | No ray-based visibility or free-space proof is produced. Unknown space must stay unknown. |
| Performance | The CLI records processing and audited end-to-end latency, deadline misses, snapshot payload, and worker RSS. It does not establish a real-time guarantee or measure viewer memory and rendering FPS. |
| Input | Dataset replay expects poses, calibration, and ordered timestamps. Per-point timestamps and scan deskew are unavailable. No live sensor ingestion exists. |

The [current-state audit](docs/spec-driven/drishti-perception/CURRENT_STATE.md) lists code evidence for each gap. The [draft PRD](docs/spec-driven/drishti-perception/PRD.md), [technical design](docs/spec-driven/drishti-perception/TECH_DESIGN.md), and [acceptance contract](docs/spec-driven/drishti-perception/ACCEPTANCE.md) define the planned work. They are pending product decisions and implementation approval.

## Setup and demo

Use Python 3.12 and the checked-in uv lockfile:

```bash
uv sync --frozen --extra viz
uv run --frozen drishti demo --output /tmp/drishti-demo-001 --view none --frames 3
```

`--output` must name a new directory. `--view record` writes a Rerun `.rrd`; `--view spawn` opens the viewer and needs the `viz` extra. A synthetic demo shows software behavior only. It does not establish real-data accuracy or timing on target hardware.

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

## Outputs

Each run writes `manifest.json`, `frames.jsonl`, and `summary.json`. A recording also writes `map.rrd`. `map_digest` supports exact replay comparison. `snapshot_array_bytes` counts array payload, while `worker_peak_rss_bytes` is the process peak. `realtime_release_gate_met` remains false because the full pipeline has not been implemented and validated.

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
