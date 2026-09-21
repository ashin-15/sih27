# Drishti-2.5 project context

## Verification

Run from this directory:

- `uv sync --frozen --extra viz`
- `uv run --frozen --extra viz pytest -q -W error`
- `uv run --frozen ruff check .`
- `uv run --frozen ruff format --check .`
- `uv run --frozen --extra viz mypy`
- `uv build --no-sources`

The viewer extra is needed for full type checking and viewer tests. Headless runtime needs only NumPy and pypatchworkpp. A wheel was installed into a separate Python 3.12 environment and exercised from /tmp without Rerun installed.

`uv run --frozen --extra viz drishti demo --output /tmp/NEW_RUN --view record` creates a deterministic synthetic plane/wall recording and JSON reports. Output directories must be new. `drishti replay --help` lists dataset replay options. Synthetic demos are not real-data accuracy or performance evaluations.

## Current scope and contracts

- Independent project: do not modify ../vrgrid-26 or the source dataset.
- Only single-frame map aggregation is implemented. Patchwork++ retains adaptive preprocessing state per engine; use a new engine for a new sequence or replay. Frames must have increasing IDs and timestamps.
- CLI, Rerun and headless consumers share MappingEngine.process and immutable MapSnapshot arrays. Do not create a second candidate mapping implementation for evaluation.
- Semantic IDs are explicitly SemanticKITTI learning IDs: 0 unknown/ignored, 1 car, through 19 traffic-sign. This differs from the reference's internal car=0 convention.
- Geometric mode never uses annotations for ground, semantics, or motion. Missing intensity remains invalid; affected points are unclassified by Patchwork++, not discarded from the map.
- Points enter mapping independently of projection winners. Original point IDs and per-point intensity are retained. Cell indices use floor(x / 0.05), then integer division for coarser levels.
- A coarse block is promoted as a whole when its footprint intersects the next finer requested region. Cells are half-open; the outer point ROI is strict. Square and radial policies are distinct.
- Heights are int32 centimetres, sums and squared sums int64, with startup overflow checks. Ground spread is descriptive population variance, not estimator uncertainty. Unsupported or ambiguous heights remain invalid. There are no clearance, free-space, or passability claims.
- Map transforms use the declared camera trajectory, sensor-to-camera calibration, and the fixed camera-to-FLU axis conversion. Subtract the first sensor translation as origin. Map x/y/z are forward/left/up relative to the converted initial camera frame, in metres. This does not estimate gravity. Visibility transforms must use the full inverse pose, not translation alone.
- Snapshot byte counts are logical array payload, not process memory or a preallocated real-time bound. Reports separate worker peak RSS, logging costs, and unmeasured viewer/scratch memory.

## Verification limitations observed 2026-09-21

- Real dataset files are ignored by the agent's file tools. Do not bypass this via shell file reads or change ignore rules; real-data acceptance requires permitted access.
- Rerun 0.29.2 records and verifies .rrd files successfully and renders the dashboard. Its native `--screenshot-to` command saved screenshots then panicked on exit with `Failed to take store hub from the Viewer` on both Wayland and X11 here. The X11 attempt also logged a surface-size validation error. No verified screenshot-exit workaround yet; do not report native viewer lifecycle as fully verified.
- Source and wheel builds succeed. Setuptools emits a nonfatal source-distribution warning that no README exists; no README was requested. MANIFEST.in includes configs, uv.lock and all test fixtures in the source distribution.
