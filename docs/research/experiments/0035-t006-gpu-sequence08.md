# Experiment 0035: full sequence-08 GPU pipeline, T-006 false-free and CPU/CUDA parity

Date: 2026-09-30. Questions: RQ-001, RQ-003, RQ-004. Host: release host (decision
0009). Code: working tree after decisions 0009/0010 and the GPU memory caps.

## Runs

Learned CUDA pipeline (in-process FRNet fp32 with NumPy interpolation, CUDA
candidates and visibility, tracking, light receipt with `--audit-every 100`,
free-cell cap 262,144) over sequence 08 in three parts, because background runs
were stopped twice by Claude Code for low system memory (see experiment 0034
addendum): frames 0-2,724, 2,725-3,518 and 3,519-4,070, each with a fresh engine.
Tracking IDs restart at the seams; semantic and false-free metrics are per scan.
All frames were accepted. Outputs are under
`C:\Users\Robin Joe\drishti-local\artifacts\` (outside OneDrive), combined by hard
links into `t006-gpu-full-seq08-combined-20260930`.

## Semantic score (4,071 scans, 499,079,562 points)

Official `evaluate_semantics.py` (pinned `a9c749e`, split valid): mIoU 0.675,
accuracy 0.923. Supplemental evaluator: mIoU 0.675473, labelled accuracy 0.922835;
0-20/20-50/50+ m mIoU 0.690758/0.543101/0.157164. Reference E-051 (authors'
CPU runtime): 0.675469 / 0.922835 / 0.690760 / 0.543065 / 0.157163.
MEASURED RESULT: the GPU runtime matches the reference to within 4e-6 mIoU.

## T-006 false-free (815 voxel frames)

`python -m drishti.visibility_evaluation` over the saved free cells:
55,072,170 free cells, 28,481,265 inside the completion volume, 28,369,908
verifiable (not invalid). Static false-free: 155,673 cells (0.549%), 0.722% by
area. Largest blocking classes: vegetation 90,356, car 39,491, trunk 8,176,
building 6,557, fence 4,216. Moving-object traces (raw IDs 252+): 1.676%.
Strata: 0-20 m 0.525%, 20-50 m 0.674%, 50 m+ 1.756% (10,419 cells); ego speed
0-5 m/s 0.328%, 5-10 m/s 0.596%, 10+ m/s 0.736%. Grid layout self-check median
IoU 0.993, minimum 0.923.

Interpretation (HYPOTHESIS): the rise with ego speed fits the missing deskew;
vegetation hits may include grass/terrain boundary labels and low vegetation
inside the tolerance band. The "occluded empty" count (27.1%) is NOT
interpretable: the checked band extends 0.2 m below the return, so it includes
subsurface voxels that are always empty and occluded. The numeric false-free
gate remains an owner decision (O-003/D-005).

## Real-data CPU/CUDA parity

`0033-real-cuda-parity.py`, frames 1,000-1,029, FRNet run once on GPU and shared:
30/30 frames identical across map cells, candidates, tracks, beam table and
summaries (deep audit on every frame). FRNet CPU vs GPU class agreement on frames
1,000/1,010/1,020: 1.0, 0.999984, 0.999976. Timings from this harness are not
evidence (two engines and a CPU model under memory pressure).

## FRNet speed options (408 scans, every 10th; whole scans; measured on battery)

| Configuration | mIoU | Accuracy | FRNet p50 |
| --- | --- | --- | --- |
| fp32, NumPy interpolation | 0.677139 | 0.923688 | 330 ms |
| fp16 autocast | 0.676587 | 0.923614 | 271 ms |
| fp32, GPU interpolation | 0.677138 | 0.923687 | 308 ms |

## Not done

The paced 100 ms check was not run: `--check-100ms` is limited to geometric mode by
design, and the laptop was on battery with the Balanced plan. The learned path
takes about 0.7-1 s per frame even on AC, so AC-008 fails as things stand.
