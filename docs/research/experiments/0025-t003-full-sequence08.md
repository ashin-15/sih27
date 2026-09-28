# Experiment 0025: full sequence 08 FRNet CPU validation

Dates: 2026-09-27 to 2026-09-28. RQ-001 / T-003. Status: COMPLETE
SEMANTIC BASELINE; T-003 acceptance remains IN PROGRESS.

The user requested continuation through the remaining T-003 scans. The first
two runs stopped after 219 and 793 scans respectively. The final evaluation
combines the saved 793-scan prefix with a new-engine continuation from scan
000793. The earlier one-scan evidence remains untouched.

## Execution and evidence

- Run root: `artifacts/t003-seq08-20260927T180705Z/` (ignored local evidence).
- Supervisor: `run.py`; status: `status.json`; exact subprocess commands:
  `commands.jsonl`; frozen wheel and revision hashes: `provenance.json`.
- Managed execution session: 54650. Follow-up heartbeat:
  `finish-t-003-sequence-08-evaluation`, every 30 minutes on this task.
- Replay artifacts: `replay/manifest.json`, `replay/frames.jsonl`,
  `replay/summary.json` when replay ends, and original-point raw-ID
  predictions under `replay/predictions/sequences/08/predictions/`.
- Pinned inputs and isolated CPU runtime are the same as experiment 0024.
  The final installed wheel is used; a copy is preserved in this run root.
  Dataset, labels and checkpoint remain read-only.

The supervisor first runs full shared-path replay. On success it checks exact
scan/prediction coverage, prediction point counts, frame order and all 4,071
accepted schema-2 semantic receipts. It then invokes the pinned official
SemanticKITTI evaluator and the supplemental class/range/unknown evaluator.
Expected result files are `coverage.json`, `scores.txt`,
`official_evaluation.log` and `range-metrics.json`. Any failure leaves an
explicit failed status and preserves prior output.

MEASURED RESULT: the first execution reached frame 218 and saved 219
consecutive predictions and receipts. It then stopped without a summary or
explicit failure record when its managed execution session and `/tmp` model
environments disappeared. Its `status.json` remained at `replay`, so it is
interrupted evidence, not a complete run. The user requested a restart. No
prior files were deleted or overwritten.

## Restart on 2026-09-28

- New run root: `artifacts/t003-seq08-restart-20260928/`.
- The pinned FRNet source, Python 3.8.20 interpreter, all 139 packages from
  the saved freeze, safe tensor export, official evaluator source and Drishti
  wheel runtime were restored under persistent ignored `artifacts/` paths.
  The safe export hash and wheel hash exactly matched the first run. The
  official source revisions remained pinned.
- A real one-scan smoke replay in `artifacts/t003-restart-smoke-20260928/`
  returned an accepted schema-2 semantic receipt. Its raw-ID prediction file
  matched the first run byte for byte at SHA-256
  `66cd44a7bb33b75c85c5b237606d086e212b11447017454d7420c008f40b0bf4`.
- The fresh 4,071-scan replay runs as user service
  `drishti-t003-seq08-20260928.service`. A service check reported `active`
  and `running`; the first four frames had consecutive IDs and accepted
  semantic receipts. The existing 30-minute follow-up now targets this
  service and the new run root.

At the restart launch, frame 000000 began with one sequence engine. Coverage,
official quality, supplemental range metrics and resource results are
pending. Estimated duration is several hours based on the prior roughly
7-second CPU model stage; this is not a completion promise.

## Shutdown checkpoint and next-session continuation

The user requested a stop before turning off the machine. `systemctl --user`
first froze the service, then thawed it briefly so systemd could stop it.
The final service state was `inactive/dead`. The final saved boundary is 793
ordered frames and predictions, IDs 000000 through 000792, with 793 accepted
schema-2 semantic receipts. `checkpoint.json` records the frame-record,
manifest and prediction-set hashes and verifies prediction point counts
against the source scans. The next frame is **000793**. The 30-minute follow-up
automation is PAUSED.

The process cannot survive power-off. Persistent isolated environments,
checkpoint/export, pinned source checkouts, wheel and predictions are under
ignored `artifacts/`, so `resume.py` can run the remaining 3,278 scans from
`--start-frame 793` in a fresh output directory. It validates the preserved
prefix before starting, then combines prediction files without changing the
source runs and performs official and range evaluation on all 4,071 scans.
Before continuation, the script was syntax checked and its prefix validator
returned 793. At that point it had not executed the remaining scans.

The continuation creates a new engine, so the combined quality report can
cover every semantic prediction, while the replay is no longer one continuous
engine/map-state run. Patchwork++ sequence state resets at the boundary;
complete continuous-path map/latency claims will require a separate run.
After machine startup, the saved hashes and runtime paths were checked and
`resume.py` started as user service
`drishti-t003-seq08-continuation-20260928.service`. Its first three output
rows cover frame IDs 000793 through 000795, each with an accepted semantic
receipt and a matching prediction file. The 30-minute follow-up is ACTIVE
again. The continuation saves `resume-status.json`, `remaining_replay.log`,
and `continuation-from-000793/` here. At launch, successful completion was
expected to produce `resume-evaluation/coverage.json`, the official `scores.txt`,
`range-metrics.json`, and evaluator logs. Final metrics were pending at launch.

T-003 remained IN PROGRESS during validation. Numeric D-005 acceptance
gates, exact public checkpoint-byte identity and separate weight terms remain
open. This run does not establish the complete-product 100 ms release gate.

## Completed combined semantic evaluation, 2026-09-28

MEASURED RESULT: the continuation service exited successfully (`Result=success`,
`ExecMainStatus=0`) and `resume-status.json` reports `completed`. The original
219-scan attempt, stopped 793-scan restart and final continuation are preserved
separately. The completed evaluation uses the restart's frames 000000..000792
and the continuation's frames 000793..004070. `resume-evaluation/coverage.json`
records 4,071 total scans, 793 prefix scans, 3,278 continuation scans and
4,071 accepted receipts. Inspection found all 4,071 ordered frame IDs, accepted
schema-2 semantic receipts and prediction files. The supervisor checked every
prediction's point count against its source scan before scoring.

The pinned official SemanticKITTI evaluator at revision
`a9c749e8124b2243b6eef1b8bcf971a9f1173a2d` completed. Its
`resume-evaluation/scores.txt` reports **0.6754690443 mIoU across 19 classes**
and **0.9228353706 labeled-point accuracy**. Supplemental
`resume-evaluation/range-metrics.json` exactly matches those overall values
over 499,079,562 points, including 476,757,723 labeled points and zero unknown
predictions. The weakest official class IoUs are motorcyclist 0.001920 and
other-ground 0.090273.

| Range | mIoU, 19 classes | Labeled accuracy | Labeled points |
| --- | ---: | ---: | ---: |
| 0-20 m | 0.690760 | 0.927338 | 420,393,089 |
| 20-50 m | 0.543065 | 0.889396 | 56,165,996 |
| 50 m and farther | 0.157163 | 0.848961 | 198,638 |

The far-range class mean has sparse labeled support and absent classes count
as zero in this report; inspect per-class unions before treating it as a
uniform far-range failure. The continuation's `summary.json` records 3,278
frames and processing p50/p95/p99 of 7,213/7,677/7,804 ms on this CPU, all
above 100 ms. Its 316,411,904-byte worker peak RSS covers the Drishti host
process, not the isolated FRNet model worker or total system memory.

Reproduction evidence is under `artifacts/t003-seq08-restart-20260928/`:
`checkpoint.json`, `provenance.json`, `resume.py`, `resume-commands.jsonl`,
`resume-status.json`, `continuation-from-000793/`, `official_evaluation.log`,
`range_evaluation.log` and `resume-evaluation/`. The checkpoint SHA-256 is
`09adea9005215641aea915cc3aa2bebf74582ce240cca91dedd07940ad94285e`;
the safe tensor export is
`4653623169f8f745907a8d7ea6a8561fed896f55dbdf421a3cd1bf86a0fe99fb`;
the frozen wheel is
`376b59738f6832d4d00a7f538b5c1a671cbfc831409fb3894699688457e5590a`.

LIMIT: this is a complete **point-semantic** sequence score. The continuation
created a new `MappingEngine`, so it does not prove continuous Patchwork++ or
map state across frame 792. It does not satisfy complete-product AC-008 or the
100 ms deadline. Numeric D-005 semantic gates, exact public checkpoint-byte
identity and separate weight terms remain open. Do not mark T-003 DONE from
the measured score alone.
