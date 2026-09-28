# Experiment 0025: full sequence 08 FRNet CPU validation

Dates: 2026-09-27 to 2026-09-28. RQ-001 / T-003. Status: STOPPED AT
FRAME 000792 AT USER REQUEST, final quality NOT VERIFIED.

The user requested continuation through the remaining T-003 scans. A fresh
continuous replay starts at scan 000000 and covers all 4,071 sequence 08
scans, retaining one engine and its sequence-specific ground state. The
earlier one-scan evidence remains untouched.

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

The restart begins at frame 000000 with one sequence engine. Coverage,
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
The script was syntax checked, and its prefix validator returned 793. **It has
not been executed for remaining scans yet.**

The continuation creates a new engine, so the combined quality report can
cover every semantic prediction, while the replay is no longer one continuous
engine/map-state run. Patchwork++ sequence state resets at the boundary;
complete continuous-path map/latency claims will require a separate run.
After machine startup, recheck the saved hashes and runtime paths, then run
`resume.py` under a managed user service. Reenable the paused task follow-up
only after the service is active. Do not restart frame 000000 or overwrite the
saved prefix unless validation shows it unusable.

T-003 remains IN PROGRESS while validation runs. Numeric D-005 acceptance
gates, exact public checkpoint-byte identity and separate weight terms remain
open. This run does not establish the complete-product 100 ms release gate.
