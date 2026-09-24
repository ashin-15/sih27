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
| C-017 | C++ SQLite recording is materially faster than Python SQLite recording for the tested 10 Hz 100-scan workload. | HYPOTHESIS | Contradicted by E-017: similar short-run read-through-commit medians and tails in standalone and concurrent tests | Rejected as a demonstrated priority, 2026-09-24; not a controlled language benchmark | T-014 |
| C-018 | Python and C++ WAL/FULL recorders completed the paced 100-scan workload during concurrent current-path replay, with read-through-commit maxima below 100 ms; that replay still missed 100 ms on every frame. | MEASURED RESULT | E-017 | High for the two 100-frame concurrent runs; Python schedule lag unrecorded and no long-run or full-product guarantee, 2026-09-24 | T-014/T-008 |
| C-019 | MCAP's durable segment boundary changes scan acknowledgement age; one-scan files met this short schedule, ten-scan files deferred ack by up to about 1.02 s. | MEASURED RESULT | E-017 | High for the three isolated 100-scan prototypes; no production MCAP durability design, 2026-09-24 | T-014 |
| C-020 | A killed SQLite writer preserved its committed row and rolled back its uncommitted row in the tested scenario; an artificial capacity limit preserved the earlier row. | MEASURED RESULT | E-018 | High for those injected conditions only, 2026-09-24 | T-014 |
| C-021 | LMDB showed lower short-run local commit tails than SQLite for all three tested 100-scan rounds, while the custom log varied across rounds. | MEASURED RESULT | E-020 | High for these exact runs; uncontrolled storage/cache conditions and no hard deadline, 2026-09-25 | T-014 |
| C-022 | An injected killed LMDB writer and artificial map limit retained only the committed prefix in the tested cases. | MEASURED RESULT | E-021 | High for these injections; physical disk and power faults NOT VERIFIED, 2026-09-25 | T-014 |
| C-023 | LMDB is the best proven production backend for no-loss live Drishti capture. | HYPOTHESIS | E-020/E-021/E-023/E-024 are prototypes without source retry, physical fault, long-duration concurrency or accepted contract evidence | NOT VERIFIED, 2026-09-25 | T-014/D-001/D-004 |
| C-024 | The tested 500-scan LMDB writer and independent reader can run alongside current replay without a recorded acquisition interval above 100 ms. | MEASURED RESULT | E-024 | High for one local run; complete processing still missed its budget and no live source exists, 2026-09-25 | T-014/T-008 |

The SIH problem statement is a REQUIREMENT source, not evidence that Drishti implements its requested behavior.
