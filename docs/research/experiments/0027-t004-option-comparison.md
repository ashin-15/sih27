# T-004 three-option screen

Date: 2026-09-28. Status: research screen, NOT a measured detector benchmark.
Question: RQ-006. User feedback from the T-004 review: compare all three
approaches before selecting the first implementation.

## Common evaluation target

The intended output is a per-scan set of evidence-only observations with
original accepted point support, learning class or unknown, observed 3D bounds
and explicit ambiguity. T-004 also asks for thin, near/far, overhang and
partial-view behavior. SemanticKITTI's [panoptic task](https://www.semantic-kitti.org/tasks.html)
measures per-point thing instances at segment IoU above 0.5. Its [evaluator](https://github.com/PRBonn/semantic-kitti-api/blob/master/evaluate_panoptic.py)
does not score 3D bounds or clearance. These require a separate reviewed
obstacle set. The existing FRNet result measures point semantics only.

| Option | What it can test next | Expected T-004 coverage | Current readiness | Main risk |
| --- | --- | --- | --- | --- |
| A. FRNet semantics plus 3D connected components | Same-path CPU fixture and held-out panoptic baseline; observed bounds from support points. | Traffic participants, pole/sign and ambiguous nonground cases can all be represented. | Input semantics and geometry already exist; no instance code or quality yes measurement yet. | Touching objects may merge; distant/thin objects may fragment; fixed clustering parameters may fail across range. |
| B. Integrate a learned panoptic instance model | Native model's held-out panoptic quality and, after adaptation, Drishti same-path quality/cost. | Potentially stronger thing-instance separation; pole/curb/overhang evidence still needs a separate rule or model. | [Panoptic-PolarNet](https://github.com/edwardzhou130/panoptic-polarnet) source and 55,095,068-byte checkpoint were cloned into `/tmp` and hash-pinned below. The supplied inference path hard-codes CUDA. [DS-Net](https://github.com/hongfz16/DS-Net) also publishes pretrained links but describes GPU-oriented inference. No learned candidate ran here. | Weight terms, dependency isolation, CPU adaptation and integration time are unverified. Published network scores are not Drishti outcomes. |
| C. Thing-only instances from FRNet plus 3D components | Smaller same-path CPU baseline and official panoptic output for supported traffic classes. | Excludes poles, curb and overhang from candidate output by design. | Same existing FRNet input as A; no instance code or measurement yet. | Cannot meet the wider FR-002/AC-002 obstacle scope alone. |

## Outcome judgment

**Best immediate development fit: A, provisional.** It can represent the full
evidence-only obstacle vocabulary without waiting for an unverified second
checkpoint, and C is an intentional subset of it. This is an inference from
interface readiness and coverage, not a measured accuracy or latency win.
**Best detector quality: UNKNOWN.** No three-way run on identical scans,
labels, point filtering, hardware or output rules exists. B could outperform
A on panoptic thing instances, but that is a hypothesis until its exact
checkpoint runs in Drishti and its broader obstacle gaps are addressed.

## Fair comparison protocol before a quality selection

1. Pin the scan split, accepted-point policy, raw-ID scatter, ground source,
   output schema, CPU hardware and stage/whole-path timing endpoints.
2. Tune A/C only on training sequences and curated development fixtures.
   Keep sequence 08 held out; use identical FRNet point predictions for A/C.
3. Verify B's code and weight terms, hash exact weights, isolate dependencies,
   prove original-point alignment and run the same held-out scans. Report any
   changed semantic backbone or extra model cost.
4. Score official panoptic PQ/SQ/RQ for supported thing classes, plus separate
   class/range/size recall and false positives on reviewed obstacle fixtures.
   Measure unknown/ambiguous coverage, CPU p50/p95/p99/max, memory and failures.
5. Choose a quality winner only if every option has comparable measured rows.
   The complete-product 100 ms CUDA release gate remains separate.

## Execution limit observed

`hf models list --search SemanticKITTI --limit 10 --format json` failed with
`Temporary failure in name resolution` on this host. The local Hub cache
contains no panoptic LiDAR checkpoint. Direct GitHub access succeeded:
`git clone --depth 1 https://github.com/edwardzhou130/Panoptic-PolarNet.git
/tmp/drishti-t004-panoptic-polarnet` resolved revision
`3a72f2380a4e505e191b69da596f521a9d9f1a71`. The included
`pretrained_weight/Panoptic_SemKITTI_PolarNet.pt` is 55,095,068 bytes,
SHA-256 `bef1c2f9df182ce90e4b555d62ca0a331209d5fc4e82a54f5f15c53b9eee672c`.
Source inspection found `torch.device('cuda:0')`, `torch.cuda.synchronize()`
and hard-coded `.cuda()` calls in instance post-processing. The checkpoint
was not unpickled or executed, and separate weight terms remain unverified.
No local accuracy, CPU latency or source/wheel Drishti compatibility follows.
The existing isolated T-003 Python 3.8 worker has Torch 1.8.1+cpu,
`torch_scatter`, `numba`, `open3d` and SciPy, but not `dropblock` (checked by
module discovery without changing that environment). CPU adaptation would
still require a new isolated worker, replacement of the hard-coded device
calls and validation of all custom operations before a fair run.
