# T-005 bounded CPU tracking slice - approved contract

Drafted 2026-09-28; APPROVED 2026-09-29 by the owner's "continue" following the explicit approval request for this contract. Research basis: [experiment 0029](research/experiments/0029-t005-tracking-screen.md).
This slice develops FR-004/AC-004 association evidence. FR-005/AC-005 motion
quality and complete release acceptance remain open.

## Scope and input

One `MappingEngine` owns one ordered sequence. In learned candidate mode, a
replaceable CPU tracker consumes only schema-3 frame-local instances whose
class is a known thing learning ID 1..8, their observed centers/bounds and
support provenance, plus the declared frame timestamp and sensor-to-map pose.
It must never read oracle instance IDs or motion labels in the inference path.
Unknown and ambiguous thin/curb/overhang candidates remain available as
frame-local obstacle evidence but do not create tracks in this first slice.
This limits false-track growth from the current broad candidate population.

Use deterministic, one-to-one association in the map frame. Gate possible
matches by equal class, positive elapsed time, center displacement and bounds
overlap; choose a fixed tie order using track ID and instance ID. Freeze the
numeric association gate and miss window from authored crossing/occlusion
fixtures before implementation, then report the exact values. A tracker may
use geometric prediction for association, but it must not publish a metric
velocity or covariance without a separately accepted AC-005 calibration and
pose-quality rule. First-frame motion is unknown.

## Lifecycle and output

- A new observation starts a tentative track. Two consecutive matched frames
  confirm it. A missed confirmed track becomes occluded for at most two
  observed frame intervals; a third miss expires it. A tentative track expires
  on its first miss. Reappearance inside the window may keep the ID only if
  the one-to-one association gate passes. A later reappearance gets a new ID.
- IDs are positive, sequence-local, monotonic and never reused, including
  after expiry. A new sequence creates a new tracker and resets its counter.
  A track can support at most one current candidate; a candidate can support
  at most one track. Capacity is bounded by a configured maximum number of
  live tracks. On capacity exhaustion, reject the new track explicitly and
  count the rejection; do not silently evict an existing confirmed track.
- Schema 4 uses `stage=tracking`, extending schema-3 candidate
  evidence with immutable `TrackEvidence` and a same-process receipt.
  `instance_id` is absent while occluded. Lifecycle, birth,
  last observation, supporting frame IDs and association confidence must
  reflect actual observations. `velocity_world_mps=None` and `velocity_covariance=None`
  until a later approved motion contract. Schema 1 to 3 remain valid.
  A rejected result cannot advance evaluator or tracker state. The engine then
fails closed; replay with a fresh engine to reset native ground state.
- Treat each update as a staged state transition. Commit new track state only
  after its immutable result passes the same-process evaluator; rejection
  preserves the prior accepted sequence state for explicit recovery.
- Invalid or nonmonotonic frame/timestamp, invalid pose, contradictory IDs or
  duplicate associations fail visibly. No frame may be silently skipped. No
  track is treated as proof of free space, solid occupancy or safe clearance.

## Bounded implementation acceptance

1. Freeze exact fixture coordinates, association distance/overlap gate and
   track capacity before production code. Cover crossing, near neighbors,
   short occlusion, reappearance after expiry, same-class ambiguity, ego
   motion past a stationary wall, first frame, empty frame, sequence reset,
   invalid timestamp and capacity exhaustion.
2. Source and installed-wheel multi-frame replay use the shared engine path,
   emit accepted schema-4 receipts, deterministic IDs and canonical digests
   for identical payload field values, with no oracle label access. Measured
   stage timings can change receipt digests across runs. Inspect saved
   lifecycle traces and explicit rejection counts.
3. Run a held-out association evaluation against sequence-consistent GT IDs.
   Report ID switches, fragmentation, false tracks, association metric,
   per-class counts, runtime and process memory. Pin and test a 4D panoptic
   evaluator or document a reproducible equivalent before comparing scores.
   The numeric AC-004 product-quality gate remains a separate owner decision.
4. Focused and full tests, Ruff, strict mypy, build, installed-wheel replay
   and `git diff --check` pass. AC-005 velocity/uncertainty and AC-008 timing
   stay NOT VERIFIED.

## Approval

The bounded association-only slice, schema-4 evidence boundary and lifecycle
policy are approved for implementation under decision 0006. The fixture gate
and capacity values below were frozen before production edits; material
changes to output meaning or product quality targets return for review.

## Frozen engineering settings and fixture expectations (2026-09-29)

DESIGN DECISION: use track-ID-ordered greedy nearest predicted center, equal
class, center distance <= min(5 m, 1.5 m + 30 m/s * elapsed seconds), and
intersection of the predicted observed bounds expanded by 0.75 m on each side
with the new observed bounds. Reject association across observation gaps >1 s.
Predict translation from the last two observed centers/timestamps only; cap
internal predictor speed at 30 m/s. Distances tie by instance ID. This is an
uncalibrated development association rule, not published velocity evidence.
Use only known thing candidates with observed status; ambiguous returns stay
frame-local. Default/maximum live capacity is 512 (configurable downward).
Store only the latest two supporting frames and center observations per track.
Emit expired tracks once, then discard their records; keep a monotonic int64
ID high-water mark. At most twice the live cap can be emitted on a transition
where old tracks expire and new ones are born. Reject new births at capacity,
record their candidate IDs, and retain their frame-local obstacle evidence.

Authored coordinates in metres, timestamps spaced by 0.1 s, each object a
0.4 m wide box centered on the listed map x/y positions: crossing objects
A=(10,-1),(10,-0.4),(10,0.2),(10,0.8) and
B=(10,1),(10,0.4),(10,-0.2),(10,-0.8) must keep their original IDs after
confirmation using the two-observation predictor. Equal-center ambiguity
selects lower instance ID first without claiming calibrated confidence.
Near neighbors at (10,0) and (10,2) keep separate IDs. Missing frames after
confirmation produce occluded, occluded, expired; reappearance before expiry
keeps ID if gated, after expiry gets a new ID. A tentative miss expires at
once. A stationary candidate at (10,0) under translated/rotated sensor poses
keeps a track while wall class 11 creates none. Empty and unknown-only frames
create no births. Capacity=1 with two eligible objects creates ID1 and records
one rejected birth. Invalid pose/timestamp or rejected payload preserves the
last accepted tracker state. A fresh engine starts sequence-local ID1.

Interface spelling follows the existing TrackEvidence fields `instance_id`,
`velocity_world_mps`, and `velocity_covariance`. A new optional tracking summary
is canonical only for schema 4, preserving schema 1-3 digests. It records
capacity, rejected births, eligible candidates and explicit frame gaps.
