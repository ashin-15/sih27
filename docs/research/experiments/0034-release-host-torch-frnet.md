# Experiment 0034: release-host setup and in-process FRNet runtime

Date: 2026-09-29 to 2026-09-30. Questions: RQ-001 (model runtime), RQ-004
(feasibility). Host: the release host of [decision 0009](../../decisions/0009-release-host-and-torch-frnet.md)
(ASUS Vivobook 16, Core 5 210H, 15.6 GiB, RTX 4050 Laptop 6 GB, driver 561.00,
Windows 11). Data: SemanticKITTI sequence 08 under `data/dataset/08`, reached
through the junction `data/semantickitti/sequences/08`; checkpoint
`data/frnet-semantickitti_seg.pth`, SHA-256 `09adea90...85e` (matches E-050).

## Environment facts

- PyTorch 2.14.0+cu126 via the new optional `model` extra (explicit CUDA 12.6
  index); CuPy 14.2.0 via `cuda`. Both import and run kernels on the GPU.
- Smart App Control first blocked unsigned native files. Most cleared on later
  loads; PyTorch's `c10_cuda.dll` (unsigned, no reputation) stayed blocked with
  Code Integrity events 3033/3077. The owner chose to turn Smart App Control
  off on 2026-09-30; it now reports Off.
- Power: the first measurements ran on battery (Windows BatteryStatus 1) with
  the Balanced plan and concurrent downloads; later runs on AC (status 2).

## In-process FRNet runtime

`frnet_model.py` reimplements only the inference path of the authors' pinned
source (range interpolation, frustum preprocessing, feature encoder, backbone,
FRHead). MEASURED RESULTS:

1. The vectorized range interpolation equals a literal port of the authors'
   loop on two 60,000-point scenes (including the point-0 quirk).
2. The checkpoint loads with `strict=True` after skipping auxiliary training
   heads; a wrong SHA-256 is rejected.
3. CPU prediction of sequence 08 scan 000000 written by the CLI has SHA-256
   `66cd44a7bb33b75c85c5b237606d086e212b11447017454d7420c008f40b0bf4`,
   byte-identical to the authors' mmdet3d runtime output recorded in
   experiment 0024 (different OS, Torch and runtime).
4. CUDA vs CPU on scan 000000: 1 class disagreement in 123,389 points; 99.9th
   percentile confidence difference 0.00072; 7 points differ by more than 0.01.
   Only 2 of 126,968 interpolated points map to a different frustum pixel,
   from device `atan2`/`arcsin` rounding. The test bounds agreement at 0.9999
   and the 99.9th percentile at 0.002.

## Release-host timing snapshots (not AC-008 evidence)

- Geometric CPU paced 100-frame check on battery with downloads running:
  100/100 misses, steady processing p50/p95 499.9/655.2 ms; stages p50
  preprocess 66.8, ground 143.5, projection 58.1, mapping 227.2 ms.
- Full GPU learned path, 5 frames on AC (median of frames 1-4): FRNet 370.8,
  ground 51.2, mapping 70.4, detector 85.1, visibility 323.6, association 3.6,
  total 962.7 ms; product receipt about 1.8 s. Every frame hit the 65,536
  free-cell cap.

## Evaluator cost

Profiling one real frame showed tuple recursion in array sealing and canonical
digesting (388,552 calls) and a Python cell-overlap loop dominating receipt
validation. Scalar-tuple fast paths (identical canonical JSON) and a packed-key
overlap check roughly halved profiled receipt time; beam-proof, free-cell and
margin checks were vectorized earlier. All evaluator rejection tests pass.

## SemanticKITTI completion voxels

The 693,975,024-byte `data_odometry_voxels.zip` was downloaded from
semantic-kitti.org (CC BY-NC-SA) and only `sequences/08/voxels` was extracted:
815 frames (every fifth scan), each with `.bin`, `.label`, `.invalid` and
`.occluded`. MEASURED: voxelizing scans with x 0..51.2 m, y -25.6..25.6 m,
z -2..4.4 m, 0.2 m, x-major order reproduces the provided input grids with IoU
0.9941, 0.9922, 0.9979, 0.9999 and 0.9668 on frames 0, 500, 1500, 2500 and
4070, confirming the layout used by `drishti.visibility_evaluation`.

## Limitations

One-scan CPU/GPU agreement; five-frame GPU timing; laptop power state varied;
no paced GPU release run yet. Full-sequence results are recorded separately.

## Addendum 2026-09-30: unbounded GPU caches and scorer correction

MEASURED RESULT: the first light-receipt full run was killed by Claude Code for
low system memory after frame 2,724, and a continuation reached 13.3 GiB private
memory after 201 frames. A probe showed process private memory rising with the
CuPy pool (1.1 -> 2.8 GiB) and PyTorch's reserved cache (2.4 GiB), from 5.1 to
7.6 GiB in 20 frames and then ratcheting on larger scans: on Windows (WDDM) the
oversubscribed VRAM is backed by system RAM. Fix: CuPy pool limit 1.5 GiB,
PyTorch `set_per_process_memory_fraction(0.4)`, and the pinned host pool released
after every CUDA frame. With the fix, private memory stayed at 6.21-6.24 GiB from
frame 20 to 80 and about 6.0 GiB during the continuation run. Outputs are
unchanged (the caps only affect caching).

Scorer correction before the final report: the first 545-frame check counted
almost every checked cell as an "occluded" hit because SemanticKITTI also marks
LiDAR-occupied voxels (including the ground under each free cell) as occluded.
Occluded hits now count only voxels that are empty in the completed scene yet
hidden from the first viewpoint. Obstacles with moving raw IDs (252+) are
reported separately as moving traces; the false-free rate counts static
non-ground voxels only. That 545-frame check is superseded.
