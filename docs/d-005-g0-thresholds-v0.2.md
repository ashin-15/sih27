# D-005 G0 threshold and resource implementation v0.2

Date: 2026-10-24. Status: **FROZEN FOR IMPLEMENTATION AND EVALUATION**.
The product owner approved D-005 v0.2 and the listed resource ceilings on
2026-10-24. This record makes the approved G0 values executable. It is not a
quality pass and does not claim that the independent final labels,
target-hardware pilot or AC-008 replay exist.

The complete contract, stable rejection/failure codes and release-run stop
policy are frozen in [decision 0013](decisions/0013-g0-complete-result-quality-resource-release-freeze.md).
This sheet owns the numeric D-005 bundle and the explicit `not-verified`
policy for quality rows whose independent reference data is not yet present.

## Versioned implementation

The runtime identifier is `d005-v0.2`, carried by the complete result together
with `drishti-g0-v1`. The values are approved for implementation and are
defined in
`Drishti-2.5/src/drishti/release_contract.py` and are checked without rounding.
Every blocking row must pass; a missing population or resource sample is
`not-verified`, not a pass.

## Semantic gates

These values carry forward the D-005 semantic sheet v0.1:

| Metric | Rule |
| --- | --- |
| Official 19-class mIoU | `>= 0.65` |
| Every official per-class IoU | `>= 0.10` |
| Supported-class mIoU, 0-20 m / 20-50 m / 50 m+ | `>= 0.60 / 0.45 / 0.20` |
| Unknown coverage, all points | `<= 0.01` |
| Unknown coverage, each range | `<= 0.02` |

The range support minimums remain 1,000,000 / 250,000 / 100,000 labeled
points, with 1,000 / 1,000 / 100 positive and union points per supported
class, and 10 / 10 / 5 supported classes. Sequence 08 remains a development
baseline, not prospective final evidence.

## Approved traffic-participant gates

The approved AC-002 values are executable for classes 1 through 8:

- mean thing PQ `>= 0.65`;
- per-class eligible recall `>= 0.70`;
- eligible recall by range `>= 0.90` near, `>= 0.85` middle and `>= 0.70` far;
- eligible recall by visible point count `>= 0.85` small, `>= 0.90` medium and
  `>= 0.90` large;
- unmatched candidates `<= 100` per 100 scans.

Each applicable row requires at least 100 eligible ground-truth instances,
and the unmatched-candidate row requires at least 1,000 annotated scans.
Wider wall, pole, curb and overhang gates remain unresolved until their
independent annotation protocol exists.

## Tracking, motion and evidence rows

The deterministic safety fixture rule is frozen in code: unsupported-free cells
must be zero. The held-out false-free ceiling, terrain quality gate, recovery
frame count and measured static/moving velocity limits remain `not-verified`
because the required independent evidence is absent. Tracking ID-switch,
fragmentation and recall rows are also blocking `not-verified` rows until an
independent trajectory-labelled final set and evaluator protocol are frozen.
Terrain/drivability, curb, drop, pothole and overhang recall/false-positive
rows are blocking `not-verified` rows until reviewed feature annotations exist.
These rows cannot be promoted by a synthetic or sequence-08 diagnostic result.

The frozen functional evidence rules are:

- unknown and stale cells are never drivable;
- diagnostic stale TTL is 2.0 seconds;
- a valid re-observation must be newer than the stale evidence before recovery;
- a measured-motion claim requires supporting frames and covariance; and
- a first-frame measured-motion claim is forbidden.

## Resource ceilings

The selected RTX 4050 laptop inventory is 15.6 GiB system RAM and 6,141 MiB
GPU memory. The implementation baseline leaves host and driver headroom:

| Resource | Ceiling |
| --- | ---: |
| Input points | 130,000 |
| Process-tree RSS | 12 GiB |
| GPU allocated memory | 5,500 MiB |
| GPU reserved memory | 5,500 MiB |
| Logical fused-map allocation | 64 MiB |
| Run-induced swap delta | 0 bytes |
| Published fused cells | 262,144 |
| Live tracks | 512 |
| Frame-local candidates | 8,192 |
| Queue depth | 2 |
| Oldest queue age | 100 ms |
| Receipt bytes | 2 MiB |
| Audit bytes | 8 MiB |
| Minimum free disk reserve | 10 GiB |

These are host-derived implementation ceilings, not measured full-path
guarantees. A complete release sample must record peak RSS, GPU allocated and
reserved memory, logical map allocation, swap, receipt, audit and disk
samples. Missing required samples remain `not-verified`, and a CUDA sample
must provide both GPU memory values.

## Remaining G0 and release items

The threshold/resource decision is approved, but G0 and release acceptance are
not marked DONE:

1. obtain the independent semantic range, wider-obstacle, tracking, terrain,
   motion and false-free evidence;
2. integrate and run the complete producer and evaluator on the selected host
   with controlled tails, resource samples and the approved release windows;
3. apply the frozen release protocol, including first-frame inclusion, zero
   misses, explicit invalid-frame handling, bounded queue behavior and
   fail-closed evaluator/audit handling.
