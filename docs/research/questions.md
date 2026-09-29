# Research questions

Status vocabulary: TODO, IN PROGRESS, BLOCKED, VALIDATION, DONE. A DONE question requires evidence and an engineering conclusion.

## RQ-001 - Learned point semantics

- Question: Under the approved target hardware and data split, which model approach meets per-point semantic quality and complete-path latency without losing original point alignment?
- Why: FR-001 and FR-008 are both required.
- Current understanding: FACT, the approved semantic-only CPU FRNet adapter runs through Drishti's shared engine path. E-050 records source/wheel one-scan compatibility; E-051 records all 4,071 sequence 08 predictions, accepted receipts and official 0.675469 mIoU. Exact upstream-byte identity and separate weight terms are unverified.
- Hypothesis: HYPOTHESIS, a replaceable checkpoint adapter can establish a measurable baseline before local training.
- Evidence required: candidate licenses/weights, exact preprocessing and class map, held-out official metrics, full-path timing and memory on target hardware.
- Falsifier: Any candidate fails class/order contract, license constraints or frozen accuracy/latency gates.
- Status: IN PROGRESS. D-002 approved FRNet for the T-003 CPU semantic slice. E-047 to E-052 record the checkpoint, class remap, isolated probe, integrated replay, full sequence 08 official/range scores and fresh CPU prediction parity/timing. Numeric D-005 gates, exact release-byte identity, weight terms and CUDA/release timing remain unverified. Conclusion: full held-out semantic baseline and CPU cost measured; release suitability UNKNOWN. Engineering impact: T-003/T-008. See `model-candidates.md`.

## RQ-006 - Single-scan obstacle instance evidence

- Question: Can a deterministic semantic and 3D geometry candidate stage preserve thin and partially seen obstacles while separating nearby objects without inventing solid occupancy?
- Why: FR-002 and T-004 require instances beyond point semantics; T-005 needs observations for association.
- Current understanding: MEASURED RESULT, the approved class-aware component detector now produces schema-3 frame-local candidates from aligned semantics, ground classes and coordinates. E-055 records source/wheel receipts and full-order panoptic scoring. SemanticKITTI panoptic scoring covers per-point thing instances, not 3D bounds or every obstacle category.
- Hypothesis: HYPOTHESIS, this replaceable CPU baseline can be improved after reviewed quality thresholds and independent wider-obstacle labels are available.
- Evidence required: independent held-out thin/curb/overhang obstacle recall and false positives, frozen AC-002 gates, and later release-path cost. Experiment 0028 now supplies the bounded class/range/size thing diagnostic and CPU baseline.
- Falsifier: merged adjacent objects, missed thin objects or false solid-volume claims beyond reviewed gates.
- Status: bounded AC-015 baseline ACCEPTED_WITH_CAVEATS; RQ-006 and full T-004 remain IN PROGRESS. Decision 0005 and experiment 0028 record the implementation, official sequence-08 score and stratified diagnostics. Full AC-002 quality remains open because numeric gates and independent wider-obstacle labels are absent. Far eligible recall is 8/30 and official motorcyclist PQ is zero.

## RQ-002 - Motion and track separation

- Question: How should ego-motion compensated observations and learned motion cues be combined without marking stationary traffic participants safe?
- Why: FR-004/005 and static map stability.
- Current understanding: FACT, geometric mode has unknown motion and no track state. Official moving-object segmentation requires temporal motion labels.
- Hypothesis: HYPOTHESIS, separate association/velocity state from semantic class and static occupancy.
- Evidence required: sequential fixtures with pose perturbation, moving IoU, velocity error, ID switches and ghost lifetime.
- Falsifier: Static walls acquire motion or collision obstacles disappear when motion is uncertain.
- Status: IN PROGRESS. Decision 0006 approves the bounded CPU slice and experiment 0030 measures its 200-frame object-observation association diagnostic. Schema-4 receipts and source/wheel replay verify the implementation. The diagnostic counted 69 ID switches, 39 fragmentations and 39 never-matched predicted track IDs; official 4D LSTQ, metric velocity and full AC-004/005 quality remain NOT VERIFIED. Engineering impact: T-005/T-006.

## RQ-003 - Conservative free-space evidence

- Question: Which ray/visibility policy minimizes false-free cells with sparse returns, occlusion and pose error at the chosen map resolutions?
- Why: FR-006/010; false-free errors affect navigation safety.
- Current understanding: FACT, current range projection has no free-space output.
- Hypothesis: HYPOTHESIS, only calibrated valid returns can support traversed free cells; no-return areas stay unknown.
- Evidence required: ray and occlusion fixtures, pose perturbations, held-out false-free metrics and bounded compute cost.
- Falsifier: Any unsupported or occluded cell is declared free under the selected policy.
- Status: IN PROGRESS for sensor-model literature; policy selection BLOCKED by D-003 and map output contract. Conclusion: UNKNOWN. Engineering impact: T-006.

## RQ-004 - Real-time feasibility

- Question: Can the entire model, detection, temporal map, audit and viewer path meet the frozen deadline on target hardware for representative sequences?
- Why: FR-008 is an end-to-end requirement.
- Current understanding: MEASURED RESULT, two 100-frame real-data headless geometric current-slice runs had 200/200 misses of the 100 ms budget. E-052 adds an unpaced 4,071-scan FRNet CPU model p50 of 7,177 ms, also far above 100 ms. The complete product path does not exist.
- Hypothesis: UNKNOWN until model and platform are selected.
- Evidence required: hardware inventory, warmup, long sequences, point-density distribution, p50/p95/p99/max, misses/drops and process/model/viewer memory.
- Falsifier: Any frozen gate fails under the declared workload.
- Status: IN PROGRESS for CPU-reference measurement; decision 0002 selects an NVIDIA CUDA host for the first-release 100 ms zero-miss replay gate, but no physical host has been inventoried. Later exact-output changes lowered current-slice work but sequence 08/00 still missed 100/100 and 82/100 strict deadlines in experiment 0016. Buffering audit after the paced loop reduced short-run misses to 2/100 and 3/100 at a minimal current-result check, but longer runs missed 28/1,000 and 3/1,000 in experiment 0019, still above the selected zero-miss rule. The present JSONL endpoint is only an audit flush, not complete machine-output publication (E-041). Complete-path feasibility is BLOCKED by NVIDIA host access, remaining D-001/D-005 payload/consumer/gate fields and T-003 to T-007. Conclusion: current CPU path fails; future CUDA path UNKNOWN. Engineering impact: T-008. See experiments 0016 and 0019 and the O-001 output-boundary audit.

## RQ-005 - Lossless acquisition under slower processing

- Question: Which durable ingress and bounded scheduler can retain every acknowledged 10 Hz scan while the current CPU worker takes more than 100 ms, and what failure contract is needed when storage or source capacity runs out?
- Why: A volatile queue does not make a scan recoverable, and continued arrival above service rate grows backlog indefinitely.
- Current understanding: MEASURED RESULT, prior SQLite/MCAP comparisons are in experiment 0008. The new C++ comparison in experiment 0009 found lower LMDB commit tails than SQLite in three short local rounds and a matched 1,000-scan pair, though LMDB's 1,000-scan acquisition p95 was slower because source-file reads varied. Injected LMDB process kill and artificial map limit preserved the committed prefix. A 500-scan LMDB writer with independent reader/current replay retained and reverified all scans, while replay still missed 100/100 processing deadlines. A separate scheduled producer in experiment 0013 preserved 100 frames with a volatile two-slot queue, but blocked on 93 queue-full events and could not sustain the source schedule.
- Hypothesis: HYPOTHESIS, one local synchronous transactional writer with indexed replay and bounded workers can separate acquisition from compute, provided the source retries or reports an acquisition fault and service eventually exceeds arrival. LMDB is the next backend prototype candidate.
- Evidence required: live source ack/retry contract, sustained contention, reader lifetime/map-growth and disk budgets, physical failure and power-fault recovery, contiguous acknowledged IDs, ordered outputs and age tails with all future stages.
- Falsifier: Acknowledged scans disappear, the source silently drops before commit, storage fills without a declared fault, or sustained service and output-age gates fail.
- Status: IN PROGRESS for technology research; live sensor input is deferred beyond the first release and production ingress integration remains BLOCKED by a source/retry and overload contract under T-001. Conclusion: LMDB is the next research prototype candidate; no backend is a proven no-loss product. Engineering impact: T-014 and any later live T-008 gate.
