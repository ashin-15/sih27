# SIH26053: verified solutions and remaining gaps

Historical research checked on 21 September 2026. The retired reference-project identifier in this archive was replaced with `legacy-reference` for standalone naming. The original file paths are recoverable from Git history. These findings are not measurements of the current Drishti-2.5 package; use the current assessment and acceptance documents under `docs/` for new work. Scope: the [problem statement](/home/ashin/Hackathon/SIH/SIH26053.md), `legacy-reference`, and a real-time 2.5D visualization dashboard. The user clarified that “GIS” means this dashboard, not georeferencing, route planning or a full geographic information system.

## Conclusion

Use the historical prototype's common integer lattice, block ownership, typed reductions, conservative visibility checks and bounded arrays as reference designs. Do **not** treat the repository as a finished, lossless perception-and-visualization pipeline. Several mathematically sound components are not wired into its main runtime, and the evaluation pipeline is materially different from the demonstration pipeline.

A compact 2.5D map cannot preserve arbitrary 3D geometry. The defensible objective is **no unexplained point loss, consistent coordinates, conservative obstacle preservation, and explicitly bounded representation error**. Keep original scans and provenance outside the rolling map when reversibility or later reconstruction matters.

## What was actually verified

- Reference commit: `8acbfe91ca24de4edd1305a3d59ca5c15ae5d40d`.
- Official SemanticKITTI API commit: `a9c749e8124b2243b6eef1b8bcf971a9f1173a2d`.
- Reference tests: **674 passed, 62 skipped, 0 failures**, 161.47 seconds. Six warnings concern synthetic fixtures falling back from missing SemanticKITTI poses to official KITTI poses.
- Independent checks: all 34 configured raw semantic IDs, packed instances, prediction-order negative control, official evaluator execution, projection-mask and distance-boundary counterexamples, common-lattice consistency over 100,004 coordinates, unchanged-parent restoration, and actual array allocation accounting.
- Environment: Python 3.12.14, NumPy 2.5.3, PyYAML 6.0.3, pytest 9.1.1, Patchwork++ 1.4.1.
- **Not reproduced:** real SemanticKITTI accuracy, FRNet inference, GPU parity/speed, full-sequence ghost rates, real wall registration or live dashboard performance. Dataset, checkpoint and working CUDA dependencies were unavailable here. Visualization tests also skipped without Rerun.

Evidence: [machine-readable verification](/home/ashin/Hackathon/SIH/research/sih26053/evidence/verification.json) and [pytest results](/home/ashin/Hackathon/SIH/research/sih26053/evidence/historical-reference-pytest.xml). The retired reproduction script is available only in Git history; it is not a standalone Drishti command.

Evidence labels below: **Local** means executed here; **Code** means inspected implementation; **Research** means primary-source support; **Proposal** means not yet validated in this project. Passing a test that documents a limitation does not mean the limitation is solved.

## Important findings before choosing the architecture

1. **The two pipelines are not equivalent.** `src/eval/harness.py` separates moving returns into a transient layer and calls the refinement gate and traversability update. `src/run/engine.py` principally shifts, bins, scatters, fuses and clears occupancy. Its main frame path does not call those refinement, transient-tracking or traversability stages. Its binning also passes speed `0.0`. Component tests cannot establish those features as active in the demonstration pipeline. **Code.**
2. **Ignored semantic points become cars in the CPU engine.** `semantic_labels()` correctly returns `-1`, but `MapEngine.step()` changes negative IDs to `0`, the perception convention's car class. A one-point frame reproduces a stored candidate of 0. Preserve a dedicated unknown sentinel, such as the existing `CLASS_UNLABELLED=31`, throughout the eventual adapter. Do not silently fix this in the reference during a research task. **Local.**
3. **Motion is still ground truth.** `--semantics frnet` runs learned semantic classification, but `perceive()` still takes `moving` from raw dataset labels. Furthermore, the main engine does not use that flag to exclude dynamic returns from persistent fusion. **Code.**
4. **Allocation headlines omit significant runtime memory.** The default 8.94 MB number describes logical cell payload, not the engine or neural model. See the measured accounting below. **Local.**
5. **The 5/10/50 schedule is legal, but the default refinement block is too small at its 5x boundary.** A 50 cm cell needs 25 children at 10 cm; a 16-cell block cannot hold them. The pool refuses that refinement. A bigger block or explicit unsupported-refinement status is necessary. **Code + passing pool tests.**

Sources: [main engine](/home/ashin/Hackathon/SIH/legacy-reference/src/run/engine.py), [perception pipeline](/home/ashin/Hackathon/SIH/legacy-reference/src/run/__main__.py), [evaluation harness](/home/ashin/Hackathon/SIH/legacy-reference/src/eval/harness.py), [refinement pool](/home/ashin/Hackathon/SIH/legacy-reference/src/grid/pool.py).

## The 15 bottlenecks and their solutions

### 01. Single-surface information loss

**Reference solution:** store ground height separately from the lowest overhead return; ground-only height aggregation avoids averaging tree canopies into the road. Initialize missing overhead height with `CEILING_NONE`, not zero. Tests reproduce canopy separation and minimum-ceiling behavior.

**Remaining gap:** two heights form an envelope, not multiple independently represented surfaces. A bridge deck and its underpass cannot both be faithfully represented by one ground estimate. The limited vertical band also rejects some height evidence.

**Decision:** retain the compact ground/clearance map as the primary display and expose vertical ambiguity explicitly. If preserving multiple surfaces is required, use a bounded multi-surface column or sparse 3D side layer only in ambiguous regions. If that layer overflows, mark it ambiguous rather than overwrite a surface. Global routing is out of scope. **Local + Proposal.**

Verify with bridge/underpass, canopy, wall, steep grade and clearance fixtures; check retained surface count and displayed clearance, not just height RMSE. [Fusion tests](/home/ashin/Hackathon/SIH/legacy-reference/tests/test_fusion.py). Multi-level surface maps explicitly address multiple surfaces and vertical intervals. [MLS paper](https://cvai.cit.tum.de/_media/spezial/bib/triebel06multi.pdf).

### 02. Many-to-one projection collisions

**Reference solution:** aggregate raw points by grid cell using fixed-point sufficient statistics; the range image is a separate representation. Losing a range-image pixel contest does **not** automatically mean losing that raw point from grid fusion.

**Remaining gap:** nearest-return projection loses farther surfaces within a pixel. Model projection and label-cache scatter also need a consistent ownership/tie rule. Reflectivity or semantic attributes can be lost or misassigned even when geometry survives.

**Decision:** keep original point indices and all raw points; define pixel ownership as minimum range with a stable point-index tie-break; unproject model outputs to every original point using the model's documented method. Count geometry, attribute and projection losses separately. Do not promise all-point semantic recovery merely because an inverse index exists. **Code + Proposal.**

Verify duplicate rays, equal-depth ties, reversed input order, invalid ranges, point index 0 and all-original-point output length. The official API's index-0 mask issue was reproduced locally; details are in the [API guide](/home/ashin/Hackathon/SIH/research/sih26053/semantic-kitti-api-guide.md). [Range-image tests](/home/ashin/Hackathon/SIH/legacy-reference/tests/test_range_image.py).

### 03. Resolution-boundary seams

**Reference solution:** common world lattice plus ownership of whole coarse blocks, rather than independently assigning each return a ring. Finer ownership requires the relevant children to fit the actual finer window. This addresses overlapping footprints and dropped points at moving/rotated boundaries.

**Remaining gap:** partition correctness does not guarantee continuous slopes, semantic features or a seam-free display. T-junction neighborhoods still have unequal spatial support. Historical observations can also remain in a ring that no longer owns their footprint.

**Decision:** preserve block-level ownership and integer-ratio levels. Use footprint-overlap queries and explicit cross-level neighborhood support for downstream features. Test ownership across frames and migration of existing evidence, not only insertion of fresh returns. **Local + Proposal.**

[Lattice tests](/home/ashin/Hackathon/SIH/legacy-reference/tests/test_lattice.py), [binning tests](/home/ashin/Hackathon/SIH/legacy-reference/tests/test_bin_points.py). Passing tested headings/speeds is not a proof of all continuous trajectories.

### 04. Unstable coordinate indexing

**Reference solution:** one base quantizer, then integer division: `i_base = x // 0.05`; `i_level = i_base // k`. Scalar and vector paths share that rule, including negative coordinates.

**Remaining gap:** decimal boundaries are not exact in binary floating point. A shared quantizer guarantees internal consistency, not exact physical placement. Some window-centering code still uses direct floating division, so do not generalize the lattice test to every coordinate operation.

**Decision:** specify one local metric origin, half-open cell convention, numeric quantizer and overflow bounds; use integer local coordinates for cell identities and derive all levels from them. Convert cells to displayed centers consistently, including the half-cell offset. No geographic CRS is required for this dashboard. **Local + Proposal.**

Independent check: 100,004 coordinates, five level ratios. Add ULP-adjacent boundaries, negative positions, large global coordinates and slot-to-world round trips to acceptance tests. [Lattice implementation](/home/ashin/Hackathon/SIH/legacy-reference/src/grid/lattice.py).

### 05. Intra-scan motion distortion

**Reference status:** not solved by the inspected runtime. It applies one rigid pose to the scan; the loader reads XYZ and remission, without per-point timing. These files alone do not establish whether upstream acquisition already compensated any distortion.

**Decision:** for live sensor ingestion, deskew points to a declared reference timestamp using per-point time and an interpolated pose trajectory. Treat unavailable timing as a documented input limitation; do not invent accurate timestamps from point order without validating that assumption. **Code + Research + Proposal.**

LIO-SAM documents its point-time, ring and IMU requirements. It is a reference for the preprocessing contract, not a drop-in claim that KITTI is deskewed. Verify straight walls during rapid translation/rotation and sweep timing offsets. [LIO-SAM](https://github.com/TixiaoShan/LIO-SAM).

### 06. Pose, clock and extrinsic errors

**Reference solution:** explicit camera/LiDAR/world transforms and calibration loading; sequence-dependent pose source. Actual code selects SemanticKITTI SLAM poses for sequences 00 and 08, official KITTI GT poses otherwise, with a retired pose-source override. Some comments still describe older behavior.

**Remaining gap:** the recorded pose-quality comparisons were not reproduced here. Ground-truth replay is not live localization, and a frame transform does not remove clock error or uncertainty. Choosing poses after evaluating on validation sequence 08 must not be presented as untouched validation.

**Decision:** pin pose provenance, extrinsics and timing in every run manifest. Use the same frame/pose source for candidate and reference maps when isolating compression error; separately measure localization error against independent evidence. Validate transforms on real static walls and loop revisits before comparing 5 cm maps. **Code + Proposal.**

For intuition, 0.1 degree orientation error produces approximately 17.5 cm transverse displacement at 100 m; finer cells cannot remove that error. [Loader](/home/ashin/Hackathon/SIH/legacy-reference/src/perception/loader.py), [frame convention tests](/home/ashin/Hackathon/SIH/legacy-reference/tests/test_frame_convention.py).

### 07. Unknown space confused with free space

**Reference solution:** observation counts, blind flags and explicit occupancy states distinguish unknown from free. Traversability includes an insufficient-evidence bit. Visibility cleanup requires a valid farther return; no return is not free-space evidence.

**Remaining gap:** the main engine does not itself update traversability. A zero-initialized traversability byte means no failure bits, so consumers must also check observation validity and update provenance. Some planning experiments permit unknown space with a penalty; that is not a safe execution policy.

**Decision:** display occupancy, traversability and validity separately, with a distinct unknown style. Do not fill holes or smooth unknown cells into apparently drivable terrain. Driving policy is outside this dashboard's scope, but the display must not imply safety where there is no evidence. **Local + Proposal.**

[Fusion tests](/home/ashin/Hackathon/SIH/legacy-reference/tests/test_fusion.py), [traversability tests](/home/ashin/Hackathon/SIH/legacy-reference/tests/test_traversability.py). Nav2 exposes unknown-space handling, but configuring it remains an integration obligation. [Nav2 costmap](https://docs.nav2.org/rolling/configuration_and_development/configuration_guide/core_servers/costmap_2d/).

### 08. Dynamic-object ghosts and state oscillation

**Reference solution:** visibility-based miss updates with a current-return guard preserve thin objects still observed. Synthetic engine tests include departed-car cleanup and a negative control without cleanup. The evaluation harness additionally separates dynamic returns and maintains transients/tracks.

**Remaining gap:** that separation is not the main engine's behavior; learned semantic classes do not provide measured motion. Occluded ghosts cannot safely be cleared just because time passed.

**Decision:** combine independently evaluated temporal motion estimation with static/transient state separation and visibility-based background clearing. A stationary car remains a collision obstacle even if it is not moving. Keep stale/occluded state distinct from confirmed absence. **Local + Research + Proposal.**

LiDAR-MOS uses ego-motion-aligned temporal residuals for motion discrimination. Evaluate moving IoU, static-object false removal, ghost lifetime and detection delay independently; model benchmark results are not this project's results. [LiDAR-MOS paper](https://arxiv.org/abs/2105.08971), [engine tests](/home/ashin/Hackathon/SIH/legacy-reference/tests/test_engine.py), [visibility tests](/home/ashin/Hackathon/SIH/legacy-reference/tests/test_visibility.py).

### 09. Cross-resolution reduction and irreversible resampling

**Reference solution:** merge using total variance: `mean = sum(w*mean_i)` and `variance = sum(w*variance_i) + sum(w*(mean_i-mean)^2)`. The second term preserves erased spatial variation. Split marks inherited children as derived and retains the parent, permitting exact restoration **only while children remain unchanged**.

**Remaining gaps:** this is not arbitrary lossless fine/coarse conversion. Default merge weights follow observation counts; a spatial-footprint query may require area weights. The split default `kappa=1/16` is 25% below the linear-square child-center geometry coefficient `1/12`. Quantized variance can hide small increases. The bounded semantic counter can lose the true majority.

**Decision:** define each field's reducer separately: footprint statistics for terrain, conservative occupied/unknown coverage for safety, minimum valid clearance, explicit semantic evidence. Use `1/12` only under its stated geometric assumptions and calibrate residual uncertainty. Preserve raw/submap detail when restoration after real information loss is needed. **Local + Proposal.**

[Split/merge tests](/home/ashin/Hackathon/SIH/legacy-reference/tests/test_splitmerge.py), [fusion tests](/home/ashin/Hackathon/SIH/legacy-reference/tests/test_fusion.py). These tests deliberately expose several limitations rather than eliminate them.

### 10. Correlated, range-dependent uncertainty

**Reference solution:** range-dependent measurement weighting, process noise, quantized variance and conservative child confidence provide useful local bookkeeping.

**Remaining gap:** returns in the same scan share pose error. Counting them as independent evidence can drive uncertainty too low. A geometric margin or capped vote count is not a calibrated probability.

**Decision:** propagate sensor and pose uncertainty into height/lateral support, add a justified uncertainty floor or effective independent-observation count, and retain submap/scan provenance for shared errors. Validate coverage of predicted intervals on held-out geometry, stratified by range and surface type. **Code + Research + Proposal.**

Robot-centric elevation mapping provides a primary reference for using pose covariance with height uncertainty; its original repository is no longer actively maintained, so use it for methodology, not as an unqualified dependency recommendation. [ANYbotics elevation mapping](https://github.com/ANYbotics/elevation_mapping).

### 11. Feature scale changes with cell size

**Reference solution:** traversability uses a physical baseline, nominally 0.5 m, rather than a fixed number of cells. Unknown-neighbor checks and explicit failure bits improve interpretation.

**Remaining gap:** coarse-level baseline approximation is not fully scale invariant. A pothole smaller than the cell can disappear before feature computation; cross-ring derivatives remain a separate problem. Semantic refinement only helps if it is enabled, fits its pool and receives new fine evidence.

**Decision:** compute slope/roughness over metric footprints; preserve safety-relevant extrema or request local refinement before discarding small features. Test identical curb, pole and pothole geometry at every range and immediately across every seam. Report detection recall alongside terrain RMSE. **Local + Proposal.**

[Traversability](/home/ashin/Hackathon/SIH/legacy-reference/src/grid/traversability.py), [feature tests](/home/ashin/Hackathon/SIH/legacy-reference/tests/test_features.py).

### 12. Layer aging and synchronization

**Reference solution:** common frame structures, transient clearing/track aging components and resetting Patchwork++ at the start of a sequence help avoid stale cross-run state.

**Remaining gap:** per-layer validity is not established merely by storing `frames_since_seen`. The main engine resets touched ages but does not implement a complete timestamped layer-lifecycle policy. Cached FRNet labels are reused at old image pixels without ego-motion warping. Sequence reset does not make a singleton estimator safe for concurrently interleaved streams.

**Decision:** publish atomic map snapshots with frame ID, timestamp, pose version, datum, resolution and per-layer freshness. Use elapsed time, not assumed frame count, for expiration under dropped frames. Own stateful perception instances per stream; reject or warp stale semantic observations. **Code + Proposal.**

Verify frame drops, reordering, two concurrent sequences, a changed pose estimate and skipped inference while turning. [Perception runtime](/home/ashin/Hackathon/SIH/legacy-reference/src/run/__main__.py), [ground tests](/home/ashin/Hackathon/SIH/legacy-reference/tests/test_ground.py).

### 13. Adaptive structures and irregular computation

**Reference solution:** structure-of-arrays, fixed-size toroidal ring buffers, sorted integer accumulation, bounded scratch and a fixed refinement pool. These are attractive for predictable local-map memory and GPU-friendly access.

**Remaining gap:** the measured allocation object is only part of runtime memory. CUDA paths, model memory and tail latency were not exercised here. Semantic and floating neural reductions are not covered by the grid's integer-determinism claim.

**Decision:** use a bounded ring-array design for the local 2.5D map; reserve a sparse 3D side layer for vertical ambiguity if needed. Avoid a pointer-heavy octree as the default hot path unless its measured benefit justifies it. A sparse structure is not automatically faster. Benchmark end-to-end p50/p95/p99 including transfers, perception, cleanup and rendering submission. **Local + Proposal.**

For a 3D comparison, nvblox is an open GPU mapping/ESDF reference, but its published speedups cannot be transplanted to this hardware or workload. [nvblox paper](https://arxiv.org/abs/2311.00626), [allocator tests](/home/ashin/Hackathon/SIH/legacy-reference/tests/test_allocators.py).

### 14. Moving-fovea allocation churn and historical evidence

**Reference solution:** world-aligned toroidal storage shifts windows and clears entering strips instead of copying whole maps. Hysteresis exists in ring-migration/refinement components; derived-parent restoration limits artificial uncertainty drift.

**Remaining gap:** the main engine's window shift is not a complete evidence transfer between resolution levels, and its runtime binning fixes speed to zero. Newly finer cells cannot acquire real detail just by copying a coarse estimate. The default 16-cell refinement pool cannot handle every legal schedule.

**Decision:** use integer window movement plus an explicit ownership transition transaction: preserve, reduce, inherit-with-provenance, or invalidate each affected field. Distinguish newly measured fine cells from inherited ones. Verify bidirectional driving, stops, heading changes, repeated boundary crossings and shifts larger than the window. **Local + Proposal.**

[Shift tests](/home/ashin/Hackathon/SIH/legacy-reference/tests/test_shift.py), [pool tests](/home/ashin/Hackathon/SIH/legacy-reference/tests/test_pool.py), [gate tests](/home/ashin/Hackathon/SIH/legacy-reference/tests/test_gate.py).

### 15. Benchmarks that hide failures

**Reference solution:** synthetic negative controls, map hashes, per-ring evaluation and optional point-attrition counters are strong reusable ideas.

**Remaining gap:** GT perception versus learned perception, differing pipelines, pose choices, present-class versus fixed-class mIoU and partial memory totals can make apparently comparable results incomparable. Skipped real-data tests are not successes. GT labels on the map input cannot demonstrate autonomous perception accuracy.

**Decision:** maintain separate map-only/oracle and end-to-end/predicted experiments. Freeze splits, preprocessing, pose source and evaluation definitions before tuning. Require point conservation and report every cap/drop/unknown category. Keep overlapping attributes, such as moving or projected, separate from terminal attrition categories. **Local + Proposal.**

For each run record: original point count; capped, outside-window, nonground, ground-out-of-band and fused-ground counts; semantic and motion provenance; per-range semantic IoU; coverage; height error; curb/pole/pothole recall; false-free cells; ghost lifetime; actual allocated/RSS/VRAM peak; latency percentiles and deadline misses. [Attrition tests](/home/ashin/Hackathon/SIH/legacy-reference/tests/test_attrition.py), [determinism tests](/home/ashin/Hackathon/SIH/legacy-reference/tests/test_determinism.py).

## Measured memory: payload is not runtime footprint

Decimal MB; CPU allocations. Extent is the reference's world-aligned 200 m by 200 m outer square, not the earlier report's illustrative circular estimate.

| Measured object | 5/10/20/40 cm | 5/10/50 cm, two transient rings |
|---|---:|---:|
| Logical cells | 745,000 | 520,000 |
| Actually allocated ring slots | 910,000 | 570,000 |
| Logical 12-byte cell payload | 8.94 MB | 6.24 MB |
| Grid arrays including toroidal padding | 10.92 MB | 6.84 MB |
| Allocator base including scatter/transient/pool/tracks | 29.06 MB | 22.98 MB |
| Additional visibility scratch | 58.24 MB | 36.48 MB |
| Allocator with visibility and pyramid | 90.41 MB | 61.55 MB |

The default `MapEngine` constructs its handle **with visibility scratch**, even in the small check with cleanup disabled: **87.30 MB** without the optional pyramid. Independently counted additional engine arrays add **46.56 MB**, bringing this selected array accounting to **at least 133.86 MB**, before perception/model buffers, Python overhead and peak temporary allocation. This is not a measured process-RSS or VRAM bound. GPU mode also retains a host mirror.

A uniform 5 cm 2.5D grid over the same square is 192 MB at 12 bytes/cell. The default grid-only allocated reduction is **17.58x**, not the logical-cell **21.48x** ratio. Do not divide a payload-only baseline by an end-to-end implementation total or vice versa. Likewise, a dense-3D ratio depends on vertical extent and bytes per voxel.

[Default allocation log](/home/ashin/Hackathon/SIH/research/sih26053/evidence/memory-default.txt), [5/10/50 allocation log](/home/ashin/Hackathon/SIH/research/sih26053/evidence/memory-5-10-50.txt). Historical sequence measurements printed by the script are inherited claims, not newly reproduced measurements.

## Real-time dashboard: the intended “GIS” scope

The deliverable is a live 2.5D map with distinct terrain/object colors and a transparent comparison against uniform high-resolution 3D storage. **No geographic CRS, map tiles, route planner or global routing graph is required.**

### What the historical prototype already provides, by code inspection

`dashboard/pipeline_view.py` provides a Rerun-based view with class/motion/ground coloring for input points, a real occupied-map surface, layer legends, timing and memory panels. `_log_occupied()` currently uses a height color ramp for map cells, while `_frame_colors()` provides semantic colors for the point cloud. Thus, semantic-colored input points are not evidence of semantic-colored **2.5D cells**. Add/test a map-cell semantic color mode for the exact problem requirement. Unpack the cell class byte and validate unknown handling first.

Its live memory time series compares against a **uniform 2.5D** grid and initializes its “allocation” value from logical cell payload. A separate `dashboard/dense3d_comparison.py` renders a reduced-footprint dense 3D comparison; it is explicitly not part of the main live dashboard. Integrate or clearly present a 3D comparison, and distinguish payload from allocated memory. These findings are code inspection, not a completed rendering/performance test. [Main dashboard](/home/ashin/Hackathon/SIH/legacy-reference/dashboard/pipeline_view.py), [3D comparison](/home/ashin/Hackathon/SIH/legacy-reference/dashboard/dense3d_comparison.py).

### Recommended dashboard contract

- **Primary map:** top-down and tilted 2.5D views of actual cells at their true sizes/heights. Show ring boundaries optionally; do not disguise a colored raw point cloud as a completed grid.
- **Color modes:** terrain/object semantics, elevation, observed/unknown and dynamic state. Provide a legend and a visible GT-versus-predicted badge. A car's semantic class does not prove that it is moving.
- **Frame consistency:** publish geometry, colors, cell sizes, frame ID and timestamp from one snapshot. Render updates from bounded buffers; expose skipped display frames and current data age. Display FPS and mapping throughput separately.
- **Memory panel:** show logical payload, allocated map arrays, total pipeline RSS/VRAM where measurable, baseline extent/resolution/bytes per voxel and whether the baseline is measured or calculated. Occupied-cell count is not allocated memory in a preallocated grid.
- **Fair 3D baseline:** the reference's 200 x 200 x 8 m volume at 5 cm has 2.56 billion voxels. At the reference's occupancy-only 1 byte/voxel assumption this is a calculated 2.56 GB, not equivalent semantic/elevation attributes. Against 10.92 MB of allocated adaptive grid arrays, the storage-only ratio is approximately 234.4x. Label those different representation payloads explicitly; do not call this a full-pipeline speedup or equal-information compression ratio. A reduced live baseline must show its smaller extent, without extrapolated memory being labeled measured.
- **Visible quality checks:** inspect seams, negative coordinates, poles, curb/pothole fixtures, canopy/ground separation and departed-object ghosts. Verify that a semantic color switch changes the cell layer, not just the input cloud.

The above is a researched dashboard recommendation. Its real-time FPS, rendering memory and model-driven cell colors still require the optional viewer, real data and target hardware to be exercised.

## Recommended implementation order

1. Freeze the point/label/frame/datum contracts and unify engine versus evaluation semantics, especially ignored IDs and motion handling.
2. Adopt common-lattice, block-ownership and array-buffer mechanisms; start with 5/10/20/40 to exercise existing refinement. Evaluate 5/10/50 separately with a suitable child-block capacity if 50 cm is required.
3. Wire and verify ground, uncertainty, transient motion, refinement and traversability in **one** end-to-end pipeline.
4. Connect actual map-cell layers to the live dashboard, with semantic colors, unknown/dynamic overlays and an explicitly scoped uniform-3D memory comparison.
5. Run held-out real-data and hardware acceptance tests before selecting a final schedule, model precision or inference rate.

Correction to the first report: `5/10/20/50` is not a compatible nested hierarchy for this engine because 50/20 is 2.5. `5/10/50` is legal; powers of two are not mandatory. The earlier circular cell-count illustration also must not be presented as measured memory for the historical prototype.

## Reproduction status

The saved reports document the bounded historical checks. The temporary environment, API clone,
and retired script are not part of the standalone project, so reproduction is NOT VERIFIED in
this working tree. The original script and unredacted artifact paths remain in Git history.
