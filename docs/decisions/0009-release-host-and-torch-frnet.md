# Decision 0009: laptop release host and in-process FRNet runtime

Date: 2026-09-29. Status: ACCEPTED (host); FRNet runtime ACCEPTED for development,
release use pending parity evidence below.

## Release host (owner instruction)

The owner said "make this laptop the release host this laptop has the nvidia gpu
use it for the necessary tasks". This supersedes the unidentified-host part of
[decision 0002](0002-cuda-replay-release-platform.md) and the development-only
assumption in [decision 0008](0008-cuda-learned-stages.md).

FACT, inventoried 2026-09-29: ASUS Vivobook 16 V3607VU; Intel Core 5 210H
(8 cores, 12 threads); 15.6 GiB RAM; NVIDIA GeForce RTX 4050 Laptop GPU,
6,141 MiB, driver 561.00 (CUDA 12.6); Windows 11 Home 10.0.26200; Windows power
plan Balanced; Smart App Control On. Release benchmarks must record power source
and plan, since a laptop GPU's clocks depend on them. The 100 ms zero-miss gate,
workload and point cap from D-001 are unchanged, not achieved.

## FRNet runtime

The authors' pinned stack (Python 3.8, Torch 1.8.1, mmcv/mmdet3d) cannot use an
RTX 40-series GPU and its worker adapter does not run on Windows. The model is not
removed: Drishti now runs FRNet in-process (`frnet_model.py`, optional `model`
extra, PyTorch CUDA 12.6 wheels) on CPU or CUDA. It reimplements only the
inference path from the authors' Apache-2.0 source at the pinned revision and
loads the original checkpoint (SHA-256 verified, `weights_only`) strictly;
auxiliary training heads are skipped. The authors' worker remains the recorded
reference runtime (`--frnet-runtime authors`, Linux).

Acceptance for release use: CPU/CUDA agreement on real scans, and sequence-08
official scores consistent with E-051 (0.675469 mIoU from the authors' runtime).
Saved prediction labels are an offline evaluation shortcut only; they never
replace the model in the product path.
