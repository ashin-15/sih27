# Interface and contract registry

Current contracts, checked 2026-09-24. Read source and tests before modifying any of these. Proposed model, detector, tracker, visibility and live-source interfaces are NOT IMPLEMENTED; see the draft technical design.

| Interface | Owner and consumers | Inputs and outputs | Invariants and compatibility | Validation |
| --- | --- | --- | --- | --- |
| CLI `drishti demo/replay` | `cli.py`; developers and report consumers | Config, new output directory, dataset/sequence or synthetic settings; manifest, frame JSONL, summary, optional Rerun recording. | Never write inside source dataset; output directory must be new; `--mode oracle` reads labels only for evaluation. Report keys are consumed as evidence; version before incompatible change. | `tests/test_cli.py`, synthetic command. |
| `ScanFrame` | `contracts.py`; dataset, demo, engine | Sequence, ID, timestamp, Nx4 sensor points, int64 original IDs, 4x4 map pose, pose source, optional annotations. | IDs unique/nonnegative and aligned; transform valid; immutable arrays; ordered frames within engine. | `tests/test_pipeline.py`, `tests/test_dataset.py`. |
| `DatasetSource.frames` | `dataset.py`; CLI | SemanticKITTI `.bin`, `.label`, `calib.txt`, `times.txt`, pose file -> `ScanFrame`. | Six-digit contiguous frame names; matching label size in oracle mode; monotonic times; calibration/pose shape. | `tests/test_dataset.py`; 100-frame real replays of sequences 00 and 08 completed on 2026-09-24. |
| `MappingEngine.process` | `pipeline.py`; CLI/viewer/evaluation | `ScanFrame -> FrameResult`. | One sequence per engine; increasing IDs/timestamps; cap `max_points`; geometric mode never reads labels; accepted points enter mapping irrespective of projection winner. | `tests/test_pipeline.py`, synthetic CLI. |
| `Annotations` and class IDs | `semantics.py`; oracle dataset and mapping | Point-aligned uint8 semantic/motion, uint16 instance. | Semantic learning ID 0 unknown/ignored, 1..19 classes; motion UNKNOWN/STATIONARY/MOVING; instance IDs are oracle annotation, not predicted tracks. | `tests/test_semantics.py`. |
| `RangeImage` | `projection.py`; engine and diagnostics | Accepted points/IDs -> pixel winners and collision/outside counts. | Projection is many-to-one; it does not remove non-winners from map. Not free-space evidence. | `tests/test_projection.py`. |
| `MapSnapshot` | `mapping.py`; CLI and Rerun | Immutable per-cell arrays and metadata. | Single frame only; cell ownership nonoverlap; unsupported/ambiguous ground invalid; observed envelopes are not solid occupancy; payload bytes are not RSS. | `tests/test_mapping.py`, `tests/test_visualization.py`. |
| `MappingConfig` | `config.py`; engine/CLI | TOML or defaults -> validated frozen config. | 5 cm base, integer nested sizes, ordered radii, point/coordinate/height and projection bounds, int64 overflow checks. `frame_budget_ms` is a threshold only. | `tests/test_config.py`. |

No tracked database schema, HTTP API, event queue, external service or deployed model interface exists. Future agents must add those here if introduced, with schema version, owner, consumer and migration behavior.
