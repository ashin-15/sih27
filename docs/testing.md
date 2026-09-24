# Testing and validation

Run package commands from `Drishti-2.5/`. Use a new output directory for each run and do not alter source scans or existing run evidence.

| Layer | Command or method | Verified 2026-09-24 | What it establishes | What it does not establish |
| --- | --- | --- | --- | --- |
| Install | `uv sync --frozen --extra viz` | NOT VERIFIED this session; existing environment was usable. | Locked dependency resolution when run successfully. | Runtime correctness or model availability. |
| Unit/integration | `uv run --frozen --extra viz pytest -q -W error` | 42 passed again on 2026-09-24. | Present contracts, mapping, CLI and viewer fixtures pass. | Learned accuracy, real sensor performance or full requirements. |
| End to end synthetic | `uv run --frozen drishti demo --output /tmp/drishti-review-baseline-20260924 --view none --frames 3` | Completed. | CLI to engine to JSON reports works for the synthetic plane/wall. | Real-data quality, viewer lifecycle or 10 Hz guarantee. |
| Lint | `uv run --frozen ruff check .` | Passed again on 2026-09-24. | Source lint. | Correct behavior. |
| Format | `uv run --frozen ruff format --check .` | Passed again, 38 files already formatted. | Source formatting. | Correct behavior. |
| Types | `uv run --frozen --extra viz mypy` | Passed again, 25 source files. | Static typing of `src` and `tests`. | Runtime/model behavior. |
| Build | `uv build --no-sources` | Passed; source and wheel built. | Source/wheel artifacts. | Installed-wheel replay until exercised separately. |
| Dataset structure | `python3 scripts/verify_semantickitti.py --root <dataset> --report <new-json> --structure-only` | PASS on 2026-09-24: all 22 sequences, 43,552 scans, 23,201 labels; report in `docs/research/experiments/`. | File names, sizes, point counts and metadata. | Scan/label content integrity, annotation correctness or inference accuracy. |
| Real replay | `uv run --frozen drishti replay --dataset <dataset> --sequence <00 or 08> --mode geometric --output <new-dir> --view none --max-frames 100` | Completed twice on 2026-09-24; both 100-frame reports saved under `Drishti-2.5/runs/`. | Real dataset load and current single-frame map path; measured CPU replay latency and accounting. | Model, temporal map, viewer, live input, safety or real-time release. |
| Replay profile | Fresh 50-frame sequence 08 CLI run plus `docs/research/experiments/0002-profile-harness.py` | Completed on 2026-09-24; harness digests and accounting matched CLI on 40 frames. | Identifies sampled mapping and audit costs; see experiment 0002. | Profiler timing is not an uninstrumented deadline result or proof of optimization. |
| Performance/model evaluation | No complete-path benchmark or learned evaluator exists. | NOT VERIFIED. | Future acceptance requires target hardware, held-out data, model hash and saved metrics. | A short demo cannot substitute. |
| Security | No dedicated scanner/gate is tracked. | UNKNOWN. | Future review should cover dataset paths, model loading and artifact provenance. | Current tests are not a security certification. |

Use the distinction: command executes; tests pass; requirements are satisfied. These are separate claims. For a bug, reproduce as near as possible to user behavior before changing code. For modified files, run focused tests plus Ruff and mypy where applicable. Broaden validation when the changed contract or acceptance risk requires it. Preserve failures in task/evidence records.
