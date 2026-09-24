# Research modules tied to development

Each module produces a short decision memo: question, primary sources, candidate options,
evidence with conditions, contradictions, conclusion (or UNKNOWN), and the concrete task affected.
Log new topics and failed candidates in `research-log.md`. A module does not approve a product
choice; the frozen product contract and accepted ADRs control implementation.

| Module | Questions and task link | Current state | Required output |
| --- | --- | --- | --- |
| R-MODEL: learned semantics and object evidence | RQ-001; T-002 to T-004 | No model, checkpoint, detector, or training workflow. `deeplearningpipeline.md` is a proposal. | Candidate preprocessing, class/point alignment, license and checkpoint provenance, official held-out quality, measured full-path cost, and detector evidence. |
| R-TIME: tracks, motion, and visibility | RQ-002/RQ-003; T-004 to T-006 | Snapshots are single-frame. Motion is unknown in geometric mode; no visibility/free-space state exists. | Sequence and pose-error tests, association/velocity metrics, ray/occlusion policy, false-free analysis, state bounds and reset behavior. |
| R-SYSTEM: evaluation and deadline | RQ-004; T-007/T-008 | Current synthetic and historical measurements do not cover the future path. Target hardware is unknown. | Reproducible dataset split and run manifest, full-path p50/p95/p99/max, deadline misses, drops, RSS/model/viewer memory, and release judgment against frozen gates. |

For each candidate, write whether the evidence changes a decision, confirms it, or is irrelevant
to it. Record metric conditions such as hardware, sequence, point count, warmup, and class map.
Never copy a benchmark number from the supplied reference archive into a Drishti claim.
