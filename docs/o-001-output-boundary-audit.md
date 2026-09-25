# O-001 output and publication boundary audit

Status: FACT about the current geometric replay path, with the selected first-release
receipt endpoint recorded below, 2026-09-25. RQ-004, D-001/D-005, O-001. This does not
approve the remaining product output schema or claim a 100 ms pass.

## Current data path

`MappingEngine.process` returns a `FrameResult` with a full in-memory
`MapSnapshot`, point observations, range image, accounting and stage timings.
In paced diagnostic replay, the CLI now passes that result to a synchronous
in-process consumer. The consumer checks identity, point alignment and array
immutability, hashes the current map, observations and range image, and returns
a receipt before the CLI writes the JSONL audit record. The CLI then discards
the result before the next scan. No versioned external machine-map writer or
complete-product evaluator is implemented; the latter's role and receipt endpoint are now selected.

| Boundary | What exists now | Missing for a complete first-release machine output |
| --- | --- | --- |
| In-memory `FrameResult` return and diagnostic receipt | Current single-frame map arrays and observations reach a synchronous diagnostic consumer, which returns a receipt after hashing them. | No implemented complete-product evaluator or frozen fused-output schema. Learned, detection and temporal fields do not exist. External acknowledgement is not the selected endpoint. |
| `frames.jsonl` Python flush | Frame ID, timestamp, input/map digests, cell count, accounting, timings and byte count. The saved [100-frame headless run](../Drishti-2.5/runs/drishti-o001-reuse-frame-arrays-seq08-100-20260925/) has an 82,553-byte JSONL file. | No cell arrays, point IDs, range image, map state or semantic evidence payload. A digest identifies a result but does not publish it. Python flush is not disk `fsync`. |
| Rerun SDK submission/flush | Geometry/ground boxes, semantic cell class colors and IDs, accepted map points, status and timings. The saved [100-frame recording](../Drishti-2.5/runs/drishti-o001-unknown-fastpath-record-flush-seq08-100-20260925/) verified with 100 geometry/raw/semantic-cell chunks each. | This is a visualization projection. It does not carry all `MapSnapshot` arrays, original point IDs, range image, motion or full provenance. SDK flush does not establish filesystem durability or rendered display. |

The current `MapSnapshot` contains level and indices, cell counts, ground
validity/span/spread, observed and obstacle height bounds, semantic evidence and
conflict, motion, intensity statistics and metadata. Several of those fields
are absent from both persisted outputs. For the headless run, the largest
snapshot array payload was 16,158,451 bytes in memory; that number is not
process RSS or a serialized file size.

A [ten-scan format screen](research/experiments/0017-snapshot-output-screen.md)
round-tripped every current `MapSnapshot` field. The median uncompressed
archive was 15.64 MB with 13.59 ms encode time, while deflate level 6 used
0.765 MB but 261.96 ms encode time. These are unpaced, current-slice format
costs, not a first-release publication benchmark.

Source: [`cli.py`](../Drishti-2.5/src/drishti/cli.py),
[`mapping.py`](../Drishti-2.5/src/drishti/mapping.py),
[`pipeline.py`](../Drishti-2.5/src/drishti/pipeline.py), and
[`visualization.py`](../Drishti-2.5/src/drishti/visualization.py), inspected
against the saved run artifacts on 2026-09-25.

## Consequence for the 100 ms gate

FACT: earlier `--check-100ms` runs measured scheduled arrival to the JSONL
audit flush, sometimes after Rerun SDK flush. Those artifacts retain their
historical source digests. The current report schema version 2 instead gates a
synchronous receipt for the implemented single-frame `FrameResult`; it records
JSONL flush age separately and excludes Rerun. This is a better current-slice
diagnostic, but it is not proof that a complete first-release map reached its
approved consumer. Changing an event label alone cannot satisfy FR-008/AC-008.

## 2026-09-25 handoff-review selection

DESIGN DECISION: the product owner selected a same-process evaluator as the first-release
consumer. Publication is receipt return after validation and acknowledgement of the complete
versioned immutable product result. Scheduled arrival and receipt use one monotonic clock;
every selected scan must meet 100 ms. Persist receipts and audit evidence. Full-payload disk
persistence is not part of this endpoint. Output is evidence-only, not planner-facing or a
navigation-safe verdict. Rerun remains outside the deadline and is measured separately.
See [decision 0002](decisions/0002-cuda-replay-release-platform.md).

The [O-001 release brief](o-001-release-profile.md) separates these selected boundaries from
still-unapproved schema checks, bounded audit/queue/failure behavior and resource limits.
The product owner explicitly deferred the proposed workload/window and density cap. A full
product payload and evaluator implementation remain prerequisites for AC-008; selecting the
consumer does not turn the current diagnostic receipt into release evidence.

UNKNOWN: required payload fields, model, numeric quality/resource gates and physical NVIDIA
host. No present artifact can be called the complete first-release output. The product
PRD/design/acceptance remain drafts, with no new runtime implementation approval. O-001 remains
IN PROGRESS.
