# Target representation: layered foveated 2.5D map (DRAFT)

Drafted 2026-09-30 at the owner's request. Status: DRAFT design, NOT IMPLEMENTED.
It defines the representation that would satisfy every SIH26053 requirement and
maps each remaining gap to a task (T-016 to T-019, plus existing T-005, T-006,
T-007, T-008 and T-015). Numeric thresholds need owner approval (D-005) before
implementation; every memory figure below is a design estimate until T-016
measures it.

## What already exists (keep)

The per-scan multi-resolution cell grid in `mapping.py`: one 5 cm base lattice,
nested 5/10/50 cm levels with integer ratios, whole-block ownership (no overlaps
or gaps), all accepted points mapped with counts conserved, integer-centimetre
heights, per-point FRNet semantics, obstacle candidates, tracks, and schema-5
current-scan occupied/observed-free/unknown evidence with beam proofs.

## Requirement to layer mapping

| SIH26053 requirement | Layer or mechanism | Task |
| --- | --- | --- |
| Variable-resolution 2.5D grid, cell size grows with distance | Existing nested lattice, held in a fixed-capacity rolling store per level | T-016 |
| No alignment errors or data loss in 3D to 2.5D | Existing lattice and ownership; exact merge/split of cell statistics when a ring boundary moves | T-016, T-015 |
| Elevation map | Elevation layer | T-016 |
| Semantic layers | Semantic layer (class evidence with bounded decay) | T-016 |
| Terrain analysis: drivable vs non-drivable | Terrain layer: semantic ground class + geometric step, slope and overhang tests | T-017 |
| Curbs, potholes, overhanging obstacles | Terrain layer features: positive step, negative step, overhang clearance | T-017 |
| Static obstacles vs dynamic objects | Motion layer: static / moving / unknown per cell and track | T-018 (with T-005) |
| Mapping in a dynamic environment | Temporal fusion, stale state and ghost clearing by ray evidence | T-006 temporal slice |
| Memory reduction vs uniform high-resolution 3D map | Fixed allocation at startup, reported against measured uniform baselines | T-016 |
| Real-time colour-coded dashboard | Rerun layers for terrain, semantics, occupancy, motion, staleness | T-019 (extends T-007) |
| Low latency, high FPS | Device-resident store and fused kernels | T-008 |
| Foveation | Speed-scaled ring radii applied to the rolling store each frame | T-015 |

## Spatial structure (T-016)

- Keep the 5 cm base lattice and levels L0 5 cm, L1 10 cm, L2 50 cm.
- Each level is a preallocated square rolling window (toroidal ring buffer)
  centred on the vehicle and shifted by whole blocks as it moves: L0 20 x 20 m,
  L1 50 x 50 m, L2 200 x 200 m. A cell is indexed by its absolute lattice key
  modulo the window, so no data moves when the vehicle moves; cells leaving the
  window are cleared, which is the explicit memory bound.
- An ownership mask marks coarse cells covered by a finer ring as delegated, so
  every location still has exactly one authoritative cell.
- Statistics are stored as additive integer sums (counts, height sums and sums of
  squares, min/max, class counts), so a coarse cell is the exact merge of its
  children and a split reassigns children without re-reading points. This is the
  "no data loss" guarantee across ring changes.

## Per-cell layers (struct of arrays, about 36 bytes per cell)

| Layer | Fields (type) | Meaning |
| --- | --- | --- |
| Elevation | ground height, ground min/max, observed min/max, obstacle min/max (int16 cm each); ground height variance (uint16, quantised) | 2.5D surface and vertical extent; heights relative to the map datum |
| Semantic | dominant class (uint8), class confidence (uint8), class-group counts: ground / static obstacle / dynamic (3 x uint16) | Semantic layer; the 19-class point labels stay per point |
| Terrain | terrain state (uint8: drivable, non-drivable terrain, obstacle, unknown); max positive step and max negative step to neighbours (int8 cm each); overhang clearance (uint8, 5 cm steps) | Drivability, curbs, potholes/drops and overhangs |
| Occupancy / visibility | state (uint8: occupied, observed-free, unknown, stale); bounded hit and miss counters (uint8 each); last observed (uint32 ms) | Evidence-only free space and freshness |
| Motion | motion state (uint8: static, moving, unknown); track reference (uint16) | Static vs dynamic |
| Provenance | update count (uint16), source flags (uint8) | Current scan vs fused, audit |

## Update rules

- **Terrain (T-017).** Drivable only if the cell has valid ground, a drivable
  semantic class (road, parking; sidewalk and terrain configurable), is observed
  (not unknown or stale), has |step| below a step threshold and slope below a
  slope threshold, and has overhang clearance above the vehicle height or no
  overhang. Positive step above the curb threshold marks a curb edge; negative
  step or missing ground inside observed-free space marks a drop or pothole
  candidate. Unknown never becomes drivable. Evidence only, not a navigation
  guarantee (D-003).
- **Motion (T-018).** A cell is moving if its points belong to a track with
  measured velocity above a threshold (needs calibrated T-005 motion) or a
  moving-object segmentation model marks them moving; static requires repeated
  observation with no displacement; otherwise unknown. Moving points update the
  motion layer but are excluded from static elevation and terrain fusion.
- **Temporal fusion (T-006 temporal slice).** Static layers fuse across scans
  with bounded counters; a cell unobserved beyond a staleness time becomes stale;
  ray evidence through a cell clears ghosts of departed objects; a current return
  always wins over a free claim.
- **Foveation (T-015).** Ring radii scale with speed for the current pose; cells
  crossing a boundary are merged or split exactly from their sums.

## Memory estimate (design arithmetic, to be measured in T-016)

| Representation | Cells or voxels | At 36 B per cell | Ratio vs layered map |
| --- | --- | --- | --- |
| Layered foveated map (L0 400 x 400, L1 500 x 500, L2 400 x 400) | 570,000 | about 20.5 MB, fixed | 1x |
| Uniform 5 cm 2.5D grid, 200 x 200 m | 16,000,000 | about 576 MB | about 28x |
| Uniform 5 cm 3D voxels, 200 x 200 x 6.4 m | 2,048,000,000 | about 2.0 GB at 1 B per voxel | about 100x |

## Output and dashboard

A versioned map-result schema (next version after schema 5) publishes the
rolling layers as per-level tiles plus the existing per-point, candidate, track
and beam-proof evidence, with the memory allocation in the manifest. The Rerun
view (T-019) colour-codes terrain state, dominant semantic group, occupancy and
staleness, and moving cells, and shows the fixed map memory against the uniform
baselines.

## Acceptance evidence to define before implementation

Exact merge/split and nonoverlap tests across moving ring boundaries; fixed
memory allocation measured at startup and constant over a full sequence;
measured memory against uniform 2.5D and 3D baselines on the same scans; terrain
fixtures (curb, pothole, overhang, slope, unknown never drivable) and a labelled
drivable-surface metric; moving-object IoU on SemanticKITTI moving labels;
stale and ghost-removal fixtures; dashboard recording inspection; latency within
the D-001 budget measured on the release host.
