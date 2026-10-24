# Decision 0013: G0 complete result, D-005, resource and release freeze

Date: 2026-10-24. Status: **FROZEN FOR IMPLEMENTATION; ACCEPTANCE NOT
VERIFIED**.

This decision records the product-owner request to freeze the complete-result
contract, D-005 gate policy, resource envelope and release replay protocol. It
freezes what must be implemented and measured. It does not claim that the
current CLI emits the complete result, that any independent final quality set
passes, or that AC-008 has passed.

Decision 0013 extends decision 0012. Where this record is more specific, it is
the authoritative G0 contract. The existing schema-1 through schema-5
contracts remain compatible under the policy below.

## 1. Complete-result schema

### 1.1 Identity and stage

- Product result schema version: **6**.
- Contract identifier: **`drishti-g0-v1`**.
- Complete-stage discriminator: **`stage=complete`**.
- A complete result is legal only after learned semantic prediction,
  candidate detection, sequence-owned tracking, current-scan visibility and
  temporal fusion have all produced payloads for the same input frame.
- The result is immutable at evaluator handoff. Arrays are C-contiguous,
  native little-endian, read-only and backed by immutable bytes.
- A successful receipt is issued only after the evaluator inspects the actual
  arrays and references. A digest-only report is not a complete result.

### 1.2 Required payload groups

| Group | Required content |
| --- | --- |
| Identity | `schema_version`, `stage`, `run_id`, `sequence_id`, `frame_id`, `scan_timestamp_ns`, `scheduled_arrival_ns`, `source_scan_digest`, `backend`, `coordinate_frame` and `units`. |
| Input and pose | Input, accepted and rejected point counts; accepted original `point_ids`; rejection counts; the 4x4 map-from-sensor pose; pose source and quality; calibration ID and digest. Accounting must conserve the input and accepted IDs must preserve input order. |
| Semantic predictions | One accepted-order `semantic_id` in learning IDs 0..19, finite confidence in 0..1, support state and explicit unknown reason for every accepted original point. ID 0 is never silently converted to a known class. |
| Motion state | Accepted-order motion state and confidence. `UNKNOWN` is a valid explicit value when measured motion is unavailable. A measured velocity claim requires supporting frames and covariance. |
| Obstacle instances | Unique frame-local instance ID, semantic ID and confidence, finite center and observed bounds, accepted point-ID support, observation timestamp, status and uncertainty. Bounds are observed evidence, not solid collision volumes. |
| Tracks | Sequence-unique track ID, instance association or prediction-only status, birth and last-observed timestamps, lifecycle, association confidence, supporting frame IDs, and world-frame velocity plus covariance or explicit unknown. No first-frame measured-motion claim is allowed. |
| Current-scan evidence | Version-5-compatible cell evidence, occupancy state, semantic evidence, ray and obstacle support, conflict state, and beam proofs. `observed_free` requires a valid beam reference and geometric proof. |
| Temporal fused map | Immutable fused cell columns described in section 1.3, including the fused summary and conservation counts. |
| Terrain state | Per-fused-cell terrain state and curb, drop and overhang flags. Unknown and stale are explicit and never become drivable by default. Pothole evidence is represented as a terrain feature result when the detector supports it; absent evidence remains unknown. |
| Provenance | Model, checkpoint, weights, class-map, calibration, code, configuration and source-scan hashes described in section 1.4; contract version, D-005 version and resource-limit bundle. |
| Diagnostics | Stage timings for load, ground, model, detector, association, visibility, fusion, transfer and evaluator; queue depth and age; dropped, invalid and rejected counts; candidate, track and map counts; process RSS; GPU allocated and reserved memory; swap delta; receipt and audit bytes; disk free reserve; and sample availability status. |

### 1.3 Fused temporal map representation

The fused map is a sequence-owned, bounded rolling map snapshot attached to
each complete result. It is not a database, a persistent map service or a
planner command. The snapshot is a columnar representation with parallel
arrays for:

- resolution `cell_sizes_cm`, level and integer cell indices;
- metric cell centres and extents;
- Kalman ground height, ground sigma and ground-validity;
- fused occupancy: `occupied`, `free`, `unknown` or `stale`;
- terrain state and terrain flags;
- dominant semantic ID and semantic evidence;
- observed obstacle low/high height envelope;
- last-seen timestamp and observation count; and
- a summary containing counts by occupancy and terrain plus feature counts.

Cell ownership is nonoverlapping across levels. The published snapshot is in
the declared map frame, preserves deterministic ordering, and contains only
state owned by the current sequence. A sequence reset discards prior tracks,
ground state and fused cells. Logical map allocation is measured separately
from process RSS.

### 1.4 Required hashes and provenance

The complete result must carry valid lowercase SHA-256 values for:

| Provenance item | Required field or bundle |
| --- | --- |
| Model identity | `model_id`, `model_source_revision`, `model_class_map_version` and `model_weights_sha256`. |
| Checkpoint | `checkpoint_sha256`, covering the exact loaded checkpoint or safe export used by the complete producer. |
| Calibration | `calibration_id` and `calibration_digest`, covering the sensor-to-map calibration and convention. |
| Code | `code_revision`, a SHA-256 of the exact source or wheel implementation used by the run. A source digest is not represented as a Git commit unless it is actually one. |
| Configuration | `config_digest`, covering mapping, model, stage, queue, resource and audit configuration. |
| Input | `source_scan_digest`, covering sequence, frame, timestamp, raw points, original IDs and pose, excluding oracle labels. |

Missing or mismatched provenance rejects a complete result. The release
manifest additionally records host, OS, driver, CUDA, power, dataset,
checkpoint-license and package-lock provenance.

### 1.5 Compatibility policy for schemas 1 through 6

| Schema | Meaning | Compatibility rule |
| --- | --- | --- |
| 1 | Geometric diagnostic result | Continue accepting valid schema-1 results with the existing canonical JSON digest. It contains no learned, instance, track, visibility or fused claims. |
| 2 | Semantic-only result | Continue accepting valid learned semantic results and their existing provenance and digest. It is not a complete result. |
| 3 | Candidate result | Continue accepting frame-local obstacle evidence. It cannot be promoted to tracking, visibility or complete by a consumer. |
| 4 | Tracking result | Continue accepting sequence-owned track evidence. Velocity may remain explicitly unknown under its existing contract. |
| 5 | Current-scan visibility result | Continue accepting current-scan beam and free-space evidence with the typed raw-array digest. It has no temporal fused state and cannot be treated as schema 6. |
| 6 | Complete result | Accept only the full G0 payload and provenance in this decision. No silent up-conversion, down-conversion or field fabrication is allowed. |

Consumers must reject unsupported future versions, preserve the schema number
in receipts and never interpret a lower-stage receipt as a complete release
receipt. Changing an existing schema's digest or field meaning requires a new
schema version.

### 1.6 Complete-stage rejection and run-failure codes

The public `ProductReceipt.error_code` and release audit use stable codes. A
runtime-specific exception may be mapped to one of these codes, but a bare
implementation exception is not a release reason code.

| Code | Meaning | Result or run action |
| --- | --- | --- |
| `R-SCHEMA-UNSUPPORTED` | Schema is unknown or stage/schema pair is invalid. | Reject result; no state advance. |
| `R-STAGE-INCOMPLETE` | Required complete-stage producer output is absent. | Reject result; no state advance. |
| `R-PROVENANCE` | Required model, checkpoint, calibration, code, config or source hash is absent or mismatched. | Reject result; no state advance. |
| `R-IDENTITY` | Source, sequence, frame, timestamp or pose identity does not match the input. | Reject result; no state advance. |
| `R-ORDER` | Frame or timestamp is nonmonotonic, duplicated or from the wrong sequence owner. | Reject result; stop release run. |
| `R-POINT-CAP` | Complete-stage input exceeds 130,000 points. | Explicit rejection; never truncate or claim success. |
| `R-ACCOUNTING` | Input, accepted, rejected, projection or support counts do not conserve. | Reject result; stop release run. |
| `R-POSE-CALIBRATION` | Pose, calibration, coordinate frame or units are invalid or inconsistent. | Reject result; stop release run. |
| `R-PAYLOAD-SEAL` | A result array is writable, aliased or not immutable bytes-backed. | Reject result; no state advance. |
| `R-PAYLOAD-SHAPE` | Required dtype, shape, range, finiteness or ID alignment fails. | Reject result; no state advance. |
| `R-INSTANCE` | Instance support, bounds, status or identity fails. | Reject result; no state advance. |
| `R-TRACK` | Track lifecycle, association, capacity or motion evidence fails. | Reject result; no state advance. |
| `R-VISIBILITY` | Beam, occupancy, conflict or current-scan visibility contract fails. | Reject result; no state advance. |
| `R-FREE-PROOF` | A free cell lacks valid ray support or fails geometric proof. | Reject result; no state advance. |
| `R-FUSED-MAP` | Fused cell geometry, ownership, terrain, occupancy or timestamps fail. | Reject result; no state advance. |
| `R-SUMMARY` | Summary counts do not match the published arrays. | Reject result; no state advance. |
| `R-RESOURCE` | A declared resource ceiling is exceeded or a required sample is invalid. | Reject result or fail run according to the resource matrix below. |

Run-level failures are recorded separately from result rejection:

`F-INVALID-FRAME`, `F-LATE-INPUT`, `F-LATE-RECEIPT`, `F-QUEUE-OVERFLOW`,
`F-MISSING-RECEIPT`, `F-DUPLICATE`, `F-SOURCE`, `F-MODEL`, `F-GROUND`,
`F-DETECTOR`, `F-TRACKER`, `F-VISIBILITY`, `F-FUSION`, `F-EVALUATOR`,
`F-RESOURCE`, `F-SWAP`, `F-AUDIT`, `F-DISK`, `F-PROCESS` and
`F-RELEASE-GATE`.

`not-verified` is a gate status, not a successful result and not a substitute
for a failure code. It blocks release acceptance whenever the affected row is
blocking.

## 2. D-005 quality thresholds

D-005 version **`d005-v0.2`** is frozen. Comparisons use unrounded values,
equality passes, and every blocking row must pass independently. Missing
population, missing labels or missing resource samples produce
`not-verified`; no aggregate score may compensate for them.

### 2.1 Semantic thresholds

| Metric | Frozen rule |
| --- | --- |
| Official 19-class mIoU | `>= 0.65` |
| Every official per-class IoU | `>= 0.10` for each learning ID 1..19 |
| Supported-class mIoU, 0-20 m / 20-50 m / 50 m+ | `>= 0.60 / 0.45 / 0.20` |
| Unknown prediction coverage, all original points | `<= 0.01` |
| Unknown prediction coverage, each range | `<= 0.02` |
| Range support | At least 1,000,000 / 250,000 / 100,000 labeled points, 1,000 / 1,000 / 100 positive and union points per supported class, and 10 / 10 / 5 supported classes. |

The final semantic evidence uses a frozen model and independent final labels.
Sequence 08 remains a development baseline, not prospective final evidence.

### 2.2 Obstacle thresholds

For traffic participants, the approved limits remain:

| Metric | Frozen rule |
| --- | --- |
| Mean thing PQ, learning IDs 1..8 | `>= 0.65` |
| Per-class eligible recall | `>= 0.70` for every class |
| Eligible recall by range | `>= 0.90` near, `>= 0.85` middle, `>= 0.70` far |
| Eligible recall by visible support | `>= 0.85` small, `>= 0.90` medium, `>= 0.90` large |
| Unmatched candidates | `<= 100` per 100 annotated scans |
| Support | At least 100 eligible ground-truth instances per class, range and size row; at least 1,000 annotated scans for unmatched candidates. |

Wall, pole, curb and overhang recall and false-positive limits require an
independent reviewed annotation protocol. Their rows are frozen as
**blocking `not-verified`**, not as an implicit pass and not as zero.

### 2.3 Tracking thresholds

The final tracking report must include ID switches per eligible trajectory,
fragmentations per eligible trajectory, false tracks, track recall, and
support counts by class and range. The rows are blocking. Their numeric limits
are **`not-verified` until an independent identity-labelled final set and
trajectory protocol are frozen**. The current 69-switch/39-fragmentation
development diagnostic is not a pass or a threshold-setting substitute.

### 2.4 Motion thresholds

The final report must include static-world velocity error, moving-object
velocity error, measured-motion unknown coverage, moving/static classification
quality where labels exist, first-frame unknown state and support counts by
range. Numeric error and unknown-coverage limits are **blocking
`not-verified` rows** until a calibrated pose and independently labelled motion
reference are frozen. Semantic class or oracle motion labels cannot satisfy
these rows.

### 2.5 Occupancy and free-space thresholds

- Unsupported-free cells on deterministic no-return, occlusion and out-of-FOV
  fixtures: **exactly 0**.
- Held-out false-free ceiling: **blocking `not-verified`** until an independent
  final completion/occupancy reference is frozen.
- Stale state: diagnostic TTL is **2.0 seconds**; stale is never treated as
  free or drivable.
- Recovery: a valid re-observation must replace stale/unknown state only after
  its evidence is accepted and ordered. The maximum measured recovery frame
  count is a blocking **`not-verified`** row until the final replay reference
  is frozen.

### 2.6 Terrain and drivability thresholds

Unknown is never drivable. The final report must include terrain/drivable IoU,
false-drivable rate, and recall and false-positive results for curb, drop,
pothole and overhang features with reviewed support counts. These numeric rows
are blocking **`not-verified`** until independent feature annotations and
measurement units are frozen. The diagnostic terrain layer is evidence only
and cannot satisfy these rows by itself.

## 3. Resource limits

The frozen baseline is for the inventoried RTX 4050 host. A ceiling is checked
against the peak or maximum observed value over the complete run, not a single
convenient sample. Missing required samples are `not-verified`.

| Resource | Frozen maximum or rule |
| --- | ---: |
| Input points | 130,000 per complete-stage frame; above-cap is an explicit rejection. |
| Process-tree RSS | 12 GiB. |
| GPU allocated memory | 5,500 MiB. |
| GPU reserved memory | 5,500 MiB. |
| Logical fused-map allocation | 64 MiB; separate from process RSS and driver allocations. |
| Published fused cells | 262,144. |
| Live tracks | 512. |
| Frame-local candidates | 8,192. |
| Queue depth | 2. |
| Oldest queued age | 100 ms. |
| Receipt output | 2 MiB per receipt. |
| Audit output | 8 MiB buffered or per-run audit bound. |
| Minimum free disk | 10 GiB reserve throughout the run. |
| Swap growth | 0 bytes run-induced delta. Any positive delta fails the run. |

The target host inventory and required configuration are:

- ASUS Vivobook 16 V3607VU;
- Intel Core 5 210H, 8 cores and 12 threads;
- 15.6 GiB system RAM;
- NVIDIA GeForce RTX 4050 Laptop GPU, 6,141 MiB;
- NVIDIA driver 561.00 and CUDA 12.6;
- Windows 11 Home 10.0.26200;
- power source and Windows power plan recorded for every run; Balanced is the
  inventoried baseline; and
- exact Python/package lock, PyTorch/CuPy build and CUDA device visibility
  recorded in the manifest.

A change of host, driver, CUDA version, power policy or model runtime requires
a new inventory and release evidence; it does not inherit a prior pass.

## 4. Release protocol

### 4.1 Exact complete replay workload

The accepted release windows are:

1. SemanticKITTI sequence **08**, all 4,071 scans, ordered at 10 Hz with a
   fresh engine and complete producer.
2. SemanticKITTI sequence **00**, all 4,541 scans, ordered at 10 Hz with a
   fresh engine and complete producer.
3. SemanticKITTI sequence **10**, frame **206** only, as a separate cold-start
   first-frame boundary case. The recorded scan has 129,392 points.

The complete-stage point cap is **130,000 points**. Above-cap input is rejected
without truncation. The release denominator includes every selected valid scan,
including the first scan in each sequence and the sequence-10 cold-start scan.

### 4.2 Warmup and timing

- Load the model, calibration, configuration and runtime before the first
  scheduled arrival.
- Warmup may use disjoint synthetic data or a disjoint sequence. Record its
  input and duration, then reset all sequence-owned state.
- Warmup may not consume, skip, pre-process or exclude any selected release
  scan.
- Use one monotonic clock. For frame index `i`,
  `scheduled_arrival_ns = t0 + i * 100,000,000`.
- Measure from scheduled arrival to the successful same-process evaluator
  receipt after complete payload validation.
- The first selected frame is included. A receipt older than 100,000,000 ns is
  a miss. Missing, rejected, duplicate or out-of-order receipts are misses or
  integrity failures as applicable.
- Report every frame age plus p50, p95, p99 and maximum, along with source
  ready time, service time, queue age, schedule lag, stage timings and resource
  samples. Rerun recording and viewer work are outside this endpoint and are
  measured separately.

### 4.3 Zero-miss and integrity policy

The clean accepted window requires exactly one successful complete receipt per
valid selected scan, in order, with zero misses, drops, duplicates, skips,
queue overflows, invalid selected frames and rejected complete results.
Invalid or above-cap fixtures used as negative tests must produce a classified
failure and must never be silently removed from the report denominator.

At the first timing miss, mark the release gate failed immediately but
continue valid remaining frames for diagnostic coverage. Do not retimestamp,
relabel or replace a late result. All other failures are fail-closed and stop
the affected run immediately after recording the failure:

| Event | Required handling |
| --- | --- |
| Invalid frame, invalid pose/time/calibration or above-cap frame | Emit `F-INVALID-FRAME` or `R-POINT-CAP`, preserve the reason and stop the run. No placeholder result is emitted. |
| Late input or receipt | Emit `F-LATE-INPUT` or `F-LATE-RECEIPT`, fail the gate immediately, and continue remaining valid frames only for diagnostics. |
| Queue overflow or queue age over 100 ms | Emit `F-QUEUE-OVERFLOW` or `R-RESOURCE`, fail and stop immediately. Never grow the queue without bound. |
| Evaluator rejection or evaluator failure | Emit the stable rejection code or `F-EVALUATOR`, do not advance state, and stop immediately. |
| Model, ground, detector, tracker, visibility or fusion failure | Emit the stage-specific `F-*` code and stop immediately. |
| Resource, swap, disk, audit or output failure | Emit `F-RESOURCE`, `F-SWAP`, `F-DISK` or `F-AUDIT` and stop immediately. |
| Duplicate, skipped, missing or out-of-order frame | Emit `F-DUPLICATE`, `F-MISSING-RECEIPT` or `F-ORDER` and stop immediately. |

At run end, drain the bounded audit queue, flush and sync the audit files,
reopen them, and verify contiguous frame IDs, counts, digests and failure
rows. Any incomplete drain or verification failure is `F-AUDIT` and the run
cannot pass.

### 4.4 Release judgment

The release is accepted only when all selected windows complete and every
blocking schema, provenance, quality, resource, timing, integrity and audit
row passes. Any `not-verified` blocking row, any stop failure or any timing
miss keeps AC-008 **NOT VERIFIED/FAILED**. This decision freezes the contract;
it does not promote the current diagnostic schema-5 CLI path to a release
producer.
