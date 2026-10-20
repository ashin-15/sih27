# Decision 0011: temporal fusion, Kalman elevation, drivability and dashboard layers

Date: 2026-10-05. Status: ACCEPTED for development.

The owner said "do temporal fusion and if applicable kalman filtering; also finish
drivable non drivable segragation we did and implement everything to the
dashboard". This approves the deferred T-006 temporal slice, the T-017 terrain
layer and the T-019 dashboard layers, using a simplified form of the T-016
rolling store. It does not approve published track velocity: a Kalman motion
filter for tracks would change the approved T-005 unknown-velocity contract and
needs a separate decision.

## Store (sequence-owned, fixed memory)

- One rolling window per resolution level, sized from the configured ring
  radius plus one cell on each side (defaults: 402 x 402 at 5 cm, 502 x 502 at
  10 cm, 402 x 402 at 50 cm), allocated once at engine start. A cell lives in
  slot `absolute key mod window`; a slot whose stored key differs, or whose key
  leaves the window around the vehicle, is reset. Memory never grows.
- Every accepted point updates the cell containing it at every level, so each
  level keeps exact statistics. The published fused map takes, for each level,
  only cells whose owner level under the current sensor position equals that
  level, so published cells never overlap (same ownership rule as `mapping.py`).
- A new engine starts a new map. The fused map is a diagnostic sequence layer in
  `FrameResult` and the dashboard; it is not yet part of the receipt-validated
  product schema.

## Per-cell fusion rules

- Ground elevation, Kalman filter (per cell, 1D): measurement = mean ground
  height of this scan's ground returns, variance = max(sample variance,
  0.03 m^2 noise floor squared) / count; process noise 0.0025 m^2/s of elapsed
  time; a jump above 0.5 m resets the cell to the measurement. Ground is valid
  when the filter standard deviation is at most 0.10 m.
- Occupancy, log-odds: +0.85 for a scan with non-ground returns in the cell,
  -0.4 when a current-scan free beam crosses it, -0.2 for a ground-only scan
  (clears departed objects without claiming free space); clamped to [-2.0, 3.5].
  OCCUPIED at >= 0.85 or whenever the current scan has a non-ground return in
  the cell; FREE at <= -0.8 only if a free beam crossed it within the staleness
  window and that free observation is newer than the last obstacle hit; STALE
  when unobserved for more than 2.0 s; otherwise UNKNOWN. The newer-evidence
  condition was verified by regression on 2026-10-14 after an old FREE state
  was reproduced following a newer hit.
- Semantics: class distribution with decay 0.8 per observation; dominant class
  among 1-19, unknown when there is no evidence.

## Terrain (drivable / non-drivable)

States: UNKNOWN, DRIVABLE, NON_DRIVABLE, OBSTACLE, STALE. Flags: curb (neighbour
higher by more than the step limit), drop (neighbour lower by more than the step
limit), overhang. Defaults: drivable classes road and parking; step limit
0.10 m between same-level 4-neighbours; vehicle clearance 2.0 m.

- STALE if stale. OBSTACLE if occupied and the obstacle bottom is less than the
  clearance above ground (or ground is invalid). An occupied cell whose obstacle
  bottom is at or above the clearance is flagged overhang and judged on its
  ground.
- DRIVABLE only with valid ground, a drivable dominant class, no curb or drop
  flag and not occupied. NON_DRIVABLE with valid ground and a non-drivable known
  class or a curb/drop flag. Everything else, including unknown semantics, is
  UNKNOWN. Unknown is never drivable. Evidence only, not a navigation guarantee
  (D-003).

## Dashboard

Rerun gains tabs for the fused terrain layer (drivable, non-drivable, obstacle,
unknown, stale, curb/drop highlights), fused occupancy, Kalman elevation, and
current-scan free space, plus fused-map counts and its fixed memory in the
status panel.

## Evidence required

Authored fixtures for Kalman convergence and reset, staleness, slot reuse and
window eviction, ghost clearing, current-return precedence, nonoverlap after
motion, and each terrain state and flag; a real sequence-08 replay; a drivability
evaluation against SemanticKITTI labels (evaluation only); dashboard inspection.

## Implementation notes (2026-10-05)

- `src/drishti/temporal.py` (`TemporalMap`, method `rolling-kalman-logodds-v1`);
  optional `MappingEngine(temporal=...)`, `FrameResult.fused`,
  `StageTimings.temporal_ms`; CLI `--temporal` with a manifest `temporal` block and a
  per-frame `temporal_summary`; Rerun tabs Terrain (fused), Occupancy (fused),
  Elevation (Kalman), Free space (current scan) and a terrain legend.
- Window side is `2 * (ceil(radius / width) + 1) + 1`: 403 / 503 / 403 cells by
  default (the estimate above said 402 / 502 / 402). Measured fixed allocation
  64,716,624 B in the first replay; 53,737,911 B (53.7 MB) after the uint8 semantic change, constant over every later replay.
- Semantic evidence is stored as uint8 (per-scan class fraction x 50, decayed), so
  `semantic_decay` is limited to (0, 0.8]; the dominant class is cached per cell.
- The obstacle bottom and top of a cell come from its latest scan with non-ground
  returns. Published ownership uses an integer-key form of the `resolve_owners`
  rule, tested equal to it for radial and square footprints.
- Free-beam evidence is used only when `--visibility` is on; otherwise occupancy
  never reaches FREE.
- Evidence: experiment 0038.
