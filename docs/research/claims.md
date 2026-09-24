# Claim registry

Use category REQUIREMENT, OBSERVATION, HYPOTHESIS, MEASURED RESULT, LITERATURE FACT or ASSUMPTION. Confidence is about the exact claim, not adjacent interpretations. Update when source or implementation changes.

| ID | Claim | Category | Evidence | Confidence / last verified | Affected components |
| --- | --- | --- | --- | --- | --- |
| C-001 | Current Drishti output is a single-frame map. | OBSERVATION | E-001, `MapSnapshot.scope` | High, 2026-09-24 | Pipeline, README |
| C-002 | Geometric mode does not infer semantic or motion labels. | OBSERVATION | E-001, `MappingEngine.process` | High, 2026-09-24 | Pipeline, viewer |
| C-003 | Existing 42 tests pass in the checked environment. | MEASURED RESULT | E-002 | High for that run, 2026-09-24 | Testing |
| C-004 | Three synthetic frames finished without a recorded 100 ms deadline miss. | MEASURED RESULT | E-003 | High for that run only, 2026-09-24 | Performance claims |
| C-005 | SemanticKITTI semantic evaluation uses per-point labels and mIoU. | LITERATURE FACT | E-004 | High, 2026-09-24 | Model evaluation |
| C-006 | A model, tracker or ray-based free-space proof is implemented. | HYPOTHESIS | Contradicted by E-001 | Rejected for current code, 2026-09-24 | Task board |
| C-007 | The full pipeline meets a real-time deadline. | HYPOTHESIS | No complete path; E-003 is insufficient | NOT VERIFIED | Release |
| C-008 | One semantic network result would prove object detection, tracking and motion quality. | HYPOTHESIS | Contradicted by E-006 and current interfaces | Rejected, 2026-09-24 | Model and evaluation plan |
| C-009 | FRNet is a viable Drishti point-semantic candidate. | HYPOTHESIS | E-007/E-008 establish availability and integration precedent only | UNKNOWN until contract, checkpoint and local evaluation | T-003 |
| C-010 | Missing returns or current height envelopes establish observed free space. | HYPOTHESIS | Contradicted by E-001/E-009 | Rejected for current code, 2026-09-24 | T-006 |
| C-011 | Current machine meets a 10 Hz, 100 ms replay budget. | HYPOTHESIS | Contradicted by E-011: 200/200 observed misses | Rejected for current path, 2026-09-24 | D-001/T-008 |
| C-012 | SemanticKITTI replay workload fits the current 150,000-point input cap. | OBSERVATION | E-012 file-size-derived counts | High for this extracted dataset's metadata, 2026-09-24; content not validated | Input capacity |
| C-013 | Row-wise `np.unique` is the dominant measured cost inside current `aggregate_cells` for the profiled sequence 08 scans. | MEASURED RESULT | E-013 | High for the sampled current path; not an optimization proof, 2026-09-24 | T-013 |
| C-014 | Packed integer grouping preserves sampled current outputs and speeds the sampled geometric `process` path, but still exceeds 100 ms p50. | MEASURED RESULT | E-014 | High for 60 sampled frames; no long-run, concurrent, CLI or full-product proof, 2026-09-24 | T-013/T-014 |
| C-015 | A queue alone guarantees both lossless 10 Hz acquisition and bounded live latency when service remains slower than 10 Hz. | HYPOTHESIS | Contradicted by E-011/E-014 and the capacity argument in experiment 0003 | Rejected under sustained overload, 2026-09-24 | T-014/D-001 |
| C-016 | The local ext4 SQLite WAL/FULL prototype stored and reverified 100 paced scans within the arrival interval. | MEASURED RESULT | E-016 | High for the short isolated run; no crash, power-loss, long-run or concurrent proof, 2026-09-24 | T-014 |

The SIH problem statement is a REQUIREMENT source, not evidence that Drishti implements its requested behavior.
