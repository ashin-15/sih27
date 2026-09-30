# Decision 0008: optional CUDA for learned candidate and visibility stages

Date: 2026-09-29. Status: ACCEPTED for development scope.

The owner said "yes install cupy, add cuda option keeping cpu reference" after
the RTX 4050 laptop GPU was confirmed. This amends the CPU-only device limits of
decisions 0005 to 0007. It does not change FRNet, which stays a CPU worker in
decision 0004's scope.

- CPU stays the reference for every stage. CUDA is optional (`--device cuda`,
  optional `cuda` extra with `cupy-cuda12x[ctk]`), and each CUDA stage must match
  the CPU payload exactly on authored and randomized fixtures.
- Detector and visibility run on the engine device; stage devices must match the
  engine so the published `backend` field is truthful. The tracker is host-only.
- ASSUMPTION (owner did not answer): this laptop is a development CUDA host, not
  the identified NVIDIA release host of decision 0002. Its timings are not
  AC-008 evidence.
  SUPERSEDED 2026-09-30 by [decision 0009](0009-release-host-and-torch-frnet.md): the
  owner made this laptop the release host.
- Output schemas are unchanged; `backend` records `cuda` when selected.

Evidence: [experiment 0032](../research/experiments/0032-cuda-stage-parity.md).
Open: real-data CPU/CUDA parity and timing need SemanticKITTI scans; GPU FRNet
needs the model assets and a separate decision.
