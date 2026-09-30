# T-006 bounded CPU visibility slice - approved contract

Drafted 2026-09-29; APPROVED 2026-09-29 by the owner's "approve all four and continue".
Implementation is authorized under [decision 0007](decisions/0007-visibility-cpu-slice.md).
Research basis: [experiment 0031](research/experiments/0031-t006-visibility-screen.md).
This slice develops FR-006/AC-006 current-scan evidence. AC-003 temporal
fusion, stale state, the numeric false-free gate (O-003/D-005), AC-010 viewer
work and AC-008 timing remain open.

## Scope and input

One `MappingEngine` owns one ordered sequence. In learned CPU mode with the
candidate and tracking stages enabled, a replaceable visibility stage consumes
the accepted current-scan points (sensor and map coordinates, original IDs,
Patchwork++ ground class, learned semantic ID), the current `MapSnapshot`
ownership, schema-3 candidate bounds and the declared `map_from_sensor` pose.
It must never read oracle labels or SSC voxels in the inference path. It holds
no state between frames in this slice: every frame's evidence source is
`CURRENT_SCAN`, and no cell is STALE.

## Cell states

Cells use the existing multiresolution ownership from `resolve_owners`; free
cells are added as new nonoverlapping cells beside the snapshot's occupied
cells.

- **OCCUPIED:** a cell with at least one current nonground return
  (`obstacle_valid`) or intersecting a candidate's observed bounds. This means
  current return evidence above the ground estimate, not a solid volume.
- **AMBIGUOUS:** a cell whose ground span is ambiguous or whose returns are
  only Patchwork++ unknown-ground, or which has semantic conflict between
  ground and nonground classes.
- **OBSERVED_FREE:** a cell with no accepted return at its level that lies on
  the supported low corridor of at least one qualifying beam (below) and is
  outside the conflict margin. Meaning: at least one ground-terminated current
  beam crossed the cell interior at no more than `tau_free` above its return
  height and no current return or candidate conflicts. It is not full-cell
  clearance, drivability, passability or navigation proof, and it cannot
  exclude objects lower than `tau_free`.
- **UNKNOWN:** everything else, including ground-only cells, no-return
  directions, out-of-FOV and ROI space, space behind any return, beam paths
  higher than `tau_free`, cells inside the conflict margin, cells beyond
  capacity and every cell when the stage is disabled or fails.

## Qualifying beams and conflict rules

A qualifying beam goes from the frame pose translation to one accepted point
that is Patchwork++ GROUND, has a learned ground semantic ID (road 9,
parking 10, sidewalk 11, other-ground 12, terrain 17), range at least
`ground_min_range_m` and lies inside the map ROI. The supported corridor is
the part of its 2D map-frame segment whose beam height is at most `tau_free`
above the return and whose horizontal distance to the return is at most
`corridor_max_m`. A cell becomes free only if the segment crosses its open
interior inside that corridor. Never free: a cell containing any accepted
return; a cell within `conflict_margin_m` in XY of any nonground,
unknown-ground, non-ground-semantic or ambiguous return, or of any candidate
bounds. Free claims never overwrite OCCUPIED or AMBIGUOUS.

Each free cell has `ray_support` equal to its count of qualifying beams and
references exactly one `BeamProof`: the supporting beam with the lowest
original point ID. Proofs are deduplicated by beam. Invalid pose, nonfinite
geometry or capacity overflow must be visible: overflow leaves remaining
cells UNKNOWN and records a counted rejection, never a silent drop.

## Output and transactions

Schema 5 uses `stage=visibility`, extending schema-4 tracking evidence with
populated `CellEvidence.occupancy`, `source`, `last_observed_ns`,
`ray_support`, `obstacle_support`, `free_beam_id`, `beams` and a canonical
visibility summary (settings, qualifying beams, free/occupied/ambiguous/
unknown counts, capacity rejections, deskew status). `uncertainty` stays -1.
The evaluator adds the existing free-proof checks to stage 5, rejects
OCCUPIED or AMBIGUOUS cells without supporting returns or candidate overlap,
rejects STALE or TEMPORAL_FUSION in this stage and rejects summary mismatch.
Schemas 1 to 4 and their digests stay unchanged. A rejected payload fails
closed like schema 4, and a schema change mid-sequence is rejected.

## Engineering settings

DESIGN DECISION, approved: `tau_free = 0.10 m`, `corridor_max_m = 5.0 m`,
`conflict_margin_m = 0.30 m`, `max_free_cells = 65,536` per frame (configurable
downward). These are development settings, not validated safety margins; the
false-free report decides whether they are kept.

## Bounded implementation acceptance

1. Authored fixtures, frozen before production code, cover rays ending
   before, at and beyond a candidate; no return; out of FOV; a cell occluded
   behind an obstacle; a low curb under a steep beam above `tau_free`; a thin
   pole within the conflict margin; ambiguous and unknown-ground endpoints; a
   non-ground semantic endpoint; corridor cap; capacity overflow; empty scan;
   translated/rotated pose equivalence; sequence reset. No invalid case may
   become free.
2. Source and installed-wheel multi-frame replay on sequence 08 emit accepted
   schema-5 receipts with deterministic visibility payload digests and no
   oracle access.
3. An offline evaluator pinned against `semantic-kitti-api` scores sequence-08
   free cells against valid SSC voxels: false-free cells and area, occluded-GT
   free cells, unknown/free/occupied coverage in the SSC volume, stratified by
   range and ego speed, plus stage time and process memory. The numeric
   false-free gate is a separate O-003/D-005 owner decision.
4. Focused and full tests, Ruff, strict mypy, build and `git diff --check`
   pass. AC-003, AC-008 and AC-010 stay NOT VERIFIED.

## Open prerequisites and risks

- UNKNOWN: whether SSC voxel files are present on the data host, their scan
  frequency and vertical offset. Without them, step 3 cannot run and the slice
  stays IN PROGRESS.
- HYPOTHESIS: a 0.30 m margin does not cover motion distortion at higher ego
  speed without deskew; the speed-stratified report tests it.
- The frozen evaluator's per-cell Python loop may be slow for tens of
  thousands of free cells; measure before changing it.

## Approval

Approved as proposed: (1) current-scan-only first slice with temporal fusion and
STALE deferred to a later slice; (2) schema 5 on top of the learned
candidate/tracking path; (3) ground-only cells staying UNKNOWN; (4) the
proposed settings above as development defaults.

## Frozen implementation rules and fixture expectations (2026-09-29)

Frozen before production edits. These make the approved rules exact; they do
not change output meaning.

- Point categories: an *obstacle* point is Patchwork++ NONGROUND or supports a
  schema-3 candidate; a *clean ground* point is Patchwork++ GROUND with a
  ground semantic ID (9, 10, 11, 12, 17); every other point is *doubtful*.
  Candidate overlap is judged by candidate support points, not by empty
  bounding-box volume, so every OCCUPIED claim has an accepted return.
- Snapshot cells: OCCUPIED if obstacle support > 0 and the ground span is not
  ambiguous; AMBIGUOUS if the ground span is ambiguous, or if the cell has no
  obstacle point and at least one doubtful point; otherwise UNKNOWN (clean
  ground only). `obstacle_support` counts obstacle points.
- Qualifying beam: clean ground return, sensor range >= `ground_min_range_m`,
  positive horizontal distance D and positive drop from origin height to the
  return. Corridor length L = min(`corridor_max_m`, `tau_free` * D / drop);
  the corridor starts at map-frame fraction max(0, 1 - L / D) of the segment.
  Samples every 0.025 m of horizontal travel from the start, strictly before
  the return; a sample counts only if it is more than 1e-6 m inside its owning
  cell (ownership from `resolve_owners`).
- Exclusions: any cell containing an accepted point at that level, using both
  the mapping key and the evaluator key. The conflict margin is conservative:
  a cell is blocked if it is within ceil(margin / width) + 1 index steps,
  Chebyshev, of any obstacle or doubtful point's cell at the same level. This
  covers the Euclidean margin.
- Free cells are sorted by (level, x index, y index); only the first
  `max_free_cells` are emitted and the rest are counted as rejected.
  `free_beam_id` and the `BeamProof.beam_id` are the lowest supporting original
  point ID.
- Schema-5 cells list snapshot cells in snapshot order, then free cells.

Authored fixtures: identity pose unless stated, ground returns at z = -1.73 m,
road semantic 9 and GROUND unless stated. Expected cells are
(level, x index, y index).

1. Beam to (20.02, 0.03): free = level 1, y 0, x 188..199; return cell
   (1, 200, 0) UNKNOWN; one proof, ray support 1.
2. Same beam plus a NONGROUND pole (class 18) at (19.5, 0.35, -1.0) and
   (19.5, 0.35, 0.5): free = x 188..190 only.
3. Steep beam to (3.02, 0.03): free = level 0, y 0, x 56..59. Adding a
   NONGROUND curb return at (2.5, 0.03, -1.65) leaves x 58..59 free; no free
   cell starts below x = 2.8 m.
4. Beam to (90.2, 0.3): capped corridor, free = level 2, y 0, x 170..179;
   (2, 169, 0) is not free.
5. No free cell for: NONGROUND building endpoint; semantic 0 endpoint;
   Patchwork++ UNKNOWN endpoint; ground endpoint with car semantic; ground
   endpoint at (2.0, 0.03) below the ground minimum range; endpoint above the
   sensor; empty scan; the region behind a wall return at (10.02, 0.03, 0).
6. `max_free_cells = 3` on fixture 1 emits (1, 188..190, 0) and counts nine
   rejected cells.
7. Pose with 90-degree yaw (exact matrix) and translation (5, -3, 0) on
   fixture 1: free = level 1, x = 49 - y_old, y = x_old - 30.
8. Frame 2 without the beam has no free cells (no carry-over); a fresh engine
   reproduces identical cell arrays.
9. The evaluator rejects a forged free ground cell, a free cell with a
   non-ground-semantic proof, a STALE cell, a summary count mismatch, a
   widened summary margin that covers fixture 2's pole, an OCCUPIED cell turned
   UNKNOWN, and a tracking-to-visibility stage change.

Clarification found by the first fixture run (2026-09-29): the T-004 detector
keeps every non-GROUND return, including Patchwork++ UNKNOWN, as candidate
support. Under the frozen obstacle rule such a cell is therefore OCCUPIED, not
AMBIGUOUS. This is more conservative and changes no free-space outcome; the
earlier "only Patchwork++ unknown-ground -> AMBIGUOUS" wording applies only to
returns that are not candidate support.
