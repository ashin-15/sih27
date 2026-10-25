# W5/W6 remaining contract decisions

2026-10-23. DRAFT FOR REVIEW. The owner authorized continuing the implementation
workflow; these previously unspecified product choices are not inferred from
that authorization. Exact internal performance work continues independently.

## Recommended bounded implementation policies

- Preserve the existing diagnostic terrain rules, five terrain states and
  curb/drop/overhang flags. Do not turn a drop into a labelled pothole without
  separate supporting truth. Keep unknown evidence explicit.
- Complete output: introduce a new versioned envelope around the current
  single-frame product plus the immutable fused arrays, sequence/frame identity,
  timestamp, configuration/method digests, state capacity and observation age.
  The evaluator must validate and digest both parts before receipt. Preserve
  schema-1-to-5 compatibility; never silently add fields to their digest stream.
- Motion: estimate map-frame displacement only from associated observed tracks
  with at least three observations and 0.2 s elapsed. Candidate thresholds for
  the development screen: moving above 0.8 m/s, stationary below 0.2 m/s,
  intermediate speeds unknown. Reassociation, misses, unsupported pose quality
  or insufficient evidence yield unknown. These are uncalibrated estimates;
  test static walls under ego motion and compare labelled moving points before
  release. Do not infer motion from class or oracle labels.
- Foveation: a forward ellipse may only refine the existing radial ownership.
  Candidate development policy: elongation factor `1 + min(speed / 10, 1)`;
  align with pose-derived travel only above 0.5 m/s, otherwise use the base
  radial policy. Known thing evidence may refine further, but model predictions
  must never coarsen a cell. Promote whole ancestor blocks and enforce capacity.
  Speed uncertainty and missing poses must be reported rather than invented.
- Layered storage: preserve bounded rolling windows and measure actual bytes.
  Additive statistics may be merged exactly; discarded fine history cannot be
  reconstructed by splitting a coarse cell. A newly refined region therefore
  starts unknown unless retained fine evidence exists. The older T-016 draft's
  unconditional exact split claim needs this correction before implementation.
- Dashboard: display the resulting evidence/age/motion and measured retained
  memory. Compare like-for-like workloads against explicit uniform 2.5D and 3D
  baselines; exclude neither scratch nor model memory from process totals.

## Decisions still needed for final acceptance

The development numbers above need explicit selection before they become a
frozen motion/foveation policy. Final numeric quality gates must be selected
before final scoring, not chosen after inspecting the final results.

Independent final obstacle, association/motion and terrain annotations are
currently UNKNOWN. A location has been requested. The existing D-005 semantic
sheet and false-free/recovery worksheet remain draft. Process-tree RSS, VRAM,
state and disk ceilings also need a selected release contract. Full sequences
08/00, sequence 10 frame 206, the 130000-point release cap, and the strict
zero-miss 100 ms rule remain selected; none is weakened here.

Completion requires these choices, the implementation, labelled quality tests,
complete receipts, measured resource bounds and a passing full paced run.
An implementation or short timing screen cannot close these acceptance items.
