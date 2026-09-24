# Open items

Updated 2026-09-24. This register records blockers and next evidence, not promises of delivery.
Close an item only with a linked decision, implementation, and validation record.

| ID | Status | Owner or decision | Open item | Next evidence |
| --- | --- | --- | --- | --- |
| O-001 | IN PROGRESS | Product owner and engineering, D-001/D-005 | Current machine, 10 Hz and 130,000 points per scan are selected as a development profile. A 100 ms complete-path goal is unmet; release hardware, miss policy, memory/disk ceiling and final gate remain unspecified. | Use experiment 0003 and a durable-ingress prototype to define throughput, output-age and overload gates after model, live scope and vehicle constraints are known. |
| O-002 | BLOCKED | Product owner, D-002 | Model strategy, allowed checkpoint/license, training split, semantic quality gate, and deployment format are unresolved. | Compare candidates under RQ-001; approve model milestone before T-003. |
| O-003 | BLOCKED | Product owner, D-003 | Navigation use, acceptable false-free rate, and handling of unknown/stale space are unresolved. | Freeze map safety contract; run RQ-003 fixtures before T-006. |
| O-004 | BLOCKED | Product owner, D-004 | Live sensor, calibration, deskew, and planner-facing output scope are unresolved. | Decide whether T-009 is in scope and define input/output contracts. |
| O-005 | TODO | Engineering, T-002 to T-006 | No learned inference, detector, tracker, measured motion, temporal state, or free-space proof exists in the active path. | Implement only after T-001 approval; validate each acceptance criterion. |
| O-006 | TODO | Engineering, T-008 | Complete-path real-time and memory guarantees are unmeasured. | Benchmark representative long sequences on target hardware with all enabled stages. |
| O-007 | IN PROGRESS | Research, RQ-001/RQ-004 | FRNet is screened as a point-semantic candidate; checkpoint terms, compatibility, and complete-path latency remain unverified. | Review exact checkpoint and preprocessing, then compare under frozen contracts using `research/model-candidates.md`. |
| O-008 | DONE | Evidence owner | Earlier report files remain absent, but the proposed model document now cites two new provenance-complete 100-frame real-data reports in unique run directories. | Preserve reports and do not reinterpret them as full-path or safety evidence. |
| O-009 | TODO | Project owner | CI, deployment, release, security review, and ownership policy are not established in this repository. | Define policy once target environment and acceptance contract are known. |
| O-010 | IN PROGRESS | Engineering research, RQ-004 | Packed int64 keys matched exact grouping, cell indices and snapshot digests on 60 real frames and cut geometric `process` p50 to 143-151 ms. Production integration and long-run validation are pending approval. | After contract approval, integrate with overflow fallback and compare fresh CLI replay outputs, latency and memory across long sequences. |
| O-011 | IN PROGRESS | Product owner and engineering, T-014 | Continuous 10 Hz arrival exceeds the measured current-path service rate. A 100-scan isolated SQLite WAL/FULL ext4 recorder test passed, but no runtime ingress, live-sensor retry contract, disk budget, stale-output policy or measured parallel scheduler exists. | Freeze overload/freshness behavior; test recorder with concurrent workers, long duration, crash/restart and disk-full faults. |

See `execution-plan.md` for task sequence and `research/modules.md` for research paired to tasks.
The first reproducible current-path measurements and remaining limits are in
`research/experiments/0001-replay-baseline-protocol.md`.
