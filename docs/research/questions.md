# Research questions

Status vocabulary: TODO, IN PROGRESS, BLOCKED, VALIDATION, DONE. A DONE question requires evidence and an engineering conclusion.

## RQ-001 - Learned point semantics

- Question: Under the approved target hardware and data split, which model approach meets per-point semantic quality and complete-path latency without losing original point alignment?
- Why: FR-001 and FR-008 are both required.
- Current understanding: FACT, there is no model adapter or checkpoint. Official SemanticKITTI semantic segmentation evaluates a label per point and mIoU.
- Hypothesis: HYPOTHESIS, a replaceable checkpoint adapter can establish a measurable baseline before local training.
- Evidence required: candidate licenses/weights, exact preprocessing and class map, held-out official metrics, full-path timing and memory on target hardware.
- Falsifier: Any candidate fails class/order contract, license constraints or frozen accuracy/latency gates.
- Status: IN PROGRESS for source and protocol review; candidate selection BLOCKED by D-001/D-002/D-005. Conclusion: UNKNOWN. Engineering impact: T-002/T-003. See `model-candidates.md`.

## RQ-002 - Motion and track separation

- Question: How should ego-motion compensated observations and learned motion cues be combined without marking stationary traffic participants safe?
- Why: FR-004/005 and static map stability.
- Current understanding: FACT, geometric mode has unknown motion and no track state. Official moving-object segmentation requires temporal motion labels.
- Hypothesis: HYPOTHESIS, separate association/velocity state from semantic class and static occupancy.
- Evidence required: sequential fixtures with pose perturbation, moving IoU, velocity error, ID switches and ghost lifetime.
- Falsifier: Static walls acquire motion or collision obstacles disappear when motion is uncertain.
- Status: TODO. Conclusion: UNKNOWN. Engineering impact: T-004/T-005/T-006.

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
- Current understanding: MEASURED RESULT, two 100-frame real-data headless current-slice runs had 200/200 misses of the 100 ms budget; the full path does not exist.
- Hypothesis: UNKNOWN until model and platform are selected.
- Evidence required: hardware inventory, warmup, long sequences, point-density distribution, p50/p95/p99/max, misses/drops and process/model/viewer memory.
- Falsifier: Any frozen gate fails under the declared workload.
- Status: IN PROGRESS for current-machine measurement; complete-path feasibility BLOCKED by D-001 release branch/D-005 and T-003 to T-007. Conclusion: current path fails the 10 Hz development goal; future path UNKNOWN. Engineering impact: T-008. See `experiments/0001-replay-baseline-protocol.md`.

## RQ-005 - Lossless acquisition under slower processing

- Question: Which durable ingress and bounded scheduler can retain every acknowledged 10 Hz scan while the current CPU worker takes more than 100 ms, and what failure contract is needed when storage or source capacity runs out?
- Why: A volatile queue does not make a scan recoverable, and continued arrival above service rate grows backlog indefinitely.
- Current understanding: MEASURED RESULT, isolated Python/C++ SQLite and MCAP recorders stored and reverified 100 paced sequence 08 scans; concurrent SQLite recorders met their 10 Hz arrival schedule while geometric replay remained below 10 Hz. See experiment 0008.
- Hypothesis: HYPOTHESIS, one local WAL/FULL writer plus indexed replay and bounded workers can separate acquisition from compute, provided the source retries or reports an acquisition fault and service eventually exceeds arrival.
- Evidence required: live source ack/retry contract, long-run contention, WAL/checkpoint and disk budgets, physical failure and power-fault recovery, contiguous acknowledged IDs, ordered outputs and age tails with all future stages.
- Falsifier: Acknowledged scans disappear, the source silently drops before commit, storage fills without a declared fault, or sustained service and output-age gates fail.
- Status: IN PROGRESS for technology research; production contract and integration BLOCKED by D-001/D-004 and T-001. Conclusion: SQLite WAL/FULL is the first prototype candidate, not a proven no-loss product. Engineering impact: T-014/T-008.
