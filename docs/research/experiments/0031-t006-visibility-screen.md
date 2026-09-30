# Experiment 0031: T-006 visibility and free-space contract screen

Date: 2026-09-29. Question: RQ-003 (with RQ-002 for later temporal state).
Scope: research and contract preparation only. No visibility code, fixture,
replay or free-space measurement was run. The workstation used for this screen
has no `data/` tree, `uv` or Python 3.12 environment, so no real-data or test
command was executed.

## Primary sources and current inputs

- FACT (SemanticKITTI dataset page, <https://semantic-kitti.org/dataset.html>,
  read 2026-09-29): each voxel sample has `.bin` (voxels occupied by laser
  measurements of the input), `.label` (labels of the *completed* scene),
  `.invalid` ("never directly seen from any position to generate the voxels",
  "not considered in the evaluation") and `.occluded` (occupied by LiDAR
  measurements or occluded by a voxel in line of sight of all poses). These
  label files are given only for training sequences 00-10.
- LITERATURE-BACKED CLAIM (Behley et al., "SemanticKITTI", ICCV 2019,
  <https://arxiv.org/abs/1904.01416>, HTML version read 2026-09-29): scene
  completion targets cover "51.2 m ahead of the car, 25.6 m to every side and
  6.4 m in height with a voxel resolution of 0.2 m" (256x256x32). Targets
  aggregate "an exhaustive number of future laser scans"; voxels without
  points are empty and never-visible voxels are ignored. Completion IoU treats
  voxels as occupied or empty.
- LITERATURE-BACKED CLAIM (E-009, OctoMap): occupied, free and unknown are
  distinct states and free space comes from traversed sensor rays.
- FACT (current code): `ScanFrame` carries only returned points with
  `deskew_status="unavailable"`; there is no per-beam ring/azimuth or
  no-return record. `RangeImage` is a many-to-one projection of accepted
  returns, not a beam table. `MapSnapshot` contains only cells that received
  accepted points. `ProductFrameResult` already reserves `Occupancy`
  (unknown/occupied/observed-free/stale/ambiguous), `EvidenceSource`,
  `last_observed_ns`, `ray_support`, `free_beam_id` and `BeamProof`. The frozen
  evaluator rejects an observed-free cell unless it references a beam whose
  origin equals the frame pose translation, whose return equals the declared
  accepted point, whose 2D segment crosses the open cell interior before the
  return, and unless no accepted point falls in that cell at its level. Stages
  1 to 4 may publish only unknown or ambiguous occupancy.

## Consequences for a conservative 2.5D policy

1. **No-return is unobservable here.** INFERENCE from the input format: a
   dropped beam and an empty direction look identical. Missing returns, out of
   FOV and behind-return space must stay UNKNOWN; this also satisfies the
   AC-006 no-return case by construction.
2. **A 2.5D ray only clears the height it travels at.** INFERENCE from
   geometry: a descending beam that ends on ground at horizontal distance `d`
   travels `s * tan(|elevation|)` above its endpoint at horizontal distance
   `s` before it. A low object under that height is not observed. With a
   free height band `tau`, only the final `tau / tan(|elevation|)` metres of a
   ground-terminated beam support low free evidence. For `tau = 0.10 m`
   this is 0.22 m at -24.8 deg, 0.71 m at -8 deg and 2.86 m at -2 deg
   (arithmetic, not measured). Nonground-terminated beams say nothing about
   the floor beneath their path.
3. **Motion distortion and pose error.** `deskew_status` is unavailable, so
   the beam origin is approximated by the frame pose. HYPOTHESIS: endpoint
   placement error grows with ego speed times sweep period and must be
   covered by a conflict margin and measured by a speed-stratified false-free
   report. Pose quality is `unverified`; current-scan free geometry is
   sensor-relative, so pose error moves the whole frame rather than one ray.
4. **Temporal fusion multiplies risk.** Carrying free evidence forward lets a
   departed or newly arrived object create ghosts or false free cells. Ownership
   levels also change as the sensor moves. A current-scan-only first slice
   avoids ghost/stale behavior until a false-free baseline exists; AC-003 stale
   state and bounded fusion then become a separate slice.
5. **Evaluation route.** Sequence 08 is a labeled validation sequence in
   SemanticKITTI 00-10, so its `.invalid/.occluded/.label` voxels can score
   Drishti free cells: a false-free cell overlaps a valid, occupied,
   non-ground GT voxel inside the claimed height band. UNKNOWN: whether the
   voxel files were downloaded to the original data host, their scan
   frequency, their exact vertical offset relative to the velodyne origin,
   and how future-scan aggregation marks dynamic-object traces. These must be
   checked against the pinned `semantic-kitti-api` before scoring. Completion
   GT is not a navigation-safety oracle.

## Decision frontier

1. **First T-006 slice:** current-scan visibility only (recommended), or
   current-scan plus bounded temporal fusion/stale state.
2. **Stage dependency:** schema 5 extends schema 4 in learned CPU mode with
   candidates and tracking enabled (recommended; candidate bounds become
   conflict evidence), or a geometric visibility-only variant.
3. **Ground-return cells:** keep them UNKNOWN occupancy with their existing
   ground fields, preserving the frozen evaluator rule (recommended), or add a
   new observed-ground state through a schema/evaluator change.
4. **Numeric engineering settings:** proposed in the T-006 contract; the
   false-free product gate stays an O-003/D-005 owner decision.

Conclusion: the current interfaces support drafting a bounded, current-scan,
ground-terminated-beam visibility slice without schema-1 changes. RQ-003
policy selection remains UNKNOWN until fixtures and a held-out false-free
report exist. No free-space, AC-003, AC-006 or AC-008 claim follows from this
screen. See the [draft T-006 contract](../../t-006-visibility-proposal.md).
