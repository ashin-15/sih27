# Hardware target screen

Updated 2026-09-25. The CUDA-backed first-release replay gate now targets an identified
NVIDIA host. The current machine remains the CPU development and parity reference; its
earlier release-machine selection was superseded by
[decision 0002](../decisions/0002-cuda-replay-release-platform.md). The exact NVIDIA host
and complete-path deadline result are NOT VERIFIED. Future vehicle targets remain research
candidates.

| Role | Candidate | Evidence and decision condition |
| --- | --- | --- |
| Selected CUDA replay release platform class; physical host pending | An identified x86_64 NVIDIA CUDA machine with measured GPU, driver, VRAM and power configuration. | Decision 0002 moves the release gate to a CUDA host. Historical vrgrid RTX 5050 results motivate a trial but do not prove Drishti speed; its T4 free-running p99 missed 100 ms. Acquire a specific host before AC-008 can run. |
| CPU development and parity reference | Intel Core Ultra 9 185H, 22 logical CPUs, integrated Intel Arc graphics and NPU, 30 GiB RAM, Linux x86_64. | Local `lscpu`, `lspci` and `free -h` describe the platform; 200 real replay frames in experiment 0001 missed the 100 ms goal. It has no NVIDIA CUDA device, so it cannot be the CUDA acceptance machine. |
| Optional model development host | Borrowed or rented x86_64 NVIDIA CUDA GPU before buying a workstation. | The [FRNet authors' install guide](https://github.com/Xiangxu-0103/FRNet/blob/master/docs/INSTALL.md) documents a CUDA/PyTorch stack and [single-GPU training/testing](https://github.com/Xiangxu-0103/FRNet/blob/master/docs/GET_STARTED.md). Its documented Python 3.8/CUDA environment is not a direct dependency match for Drishti's Python 3.12 package. Measure checkpoint memory and preprocessing before specifying VRAM or purchasing hardware. |
| Possible vehicle compute later | NVIDIA Jetson AGX Orin 64 GB developer kit, only if live deployment is approved. | [NVIDIA's developer-kit documentation](https://developer.nvidia.com/embedded/jetson-developer-kits) identifies it as an edge robotics platform. ARM package builds, sensor input, power/thermal limits, and complete-path latency must be tested; its advertised accelerator throughput is not a Drishti guarantee. |

[OpenVINO documents Intel CPU/GPU/NPU inference paths](https://docs.openvino.ai/2026/openvino-workflow/running-inference/inference-devices-and-modes/auto-device-selection.html),
so the integrated accelerator is worth a compatibility experiment after a checkpoint and model
format are chosen. There is currently no evidence that FRNet's operations export and run on the
machine's NPU or integrated GPU. [Autoware's FRNet integration](https://github.com/autowarefoundation/autoware_universe/blob/main/perception/autoware_lidar_frnet/README.md)
uses TensorRT, a separate implementation reference rather than a drop-in Python backend.

## Working target and limits

- DESIGN DECISION for development: replay SemanticKITTI at 10 Hz with up to 130,000 input points
  per scan, retaining the current 150,000-point capacity limit. Use the current laptop for the
  first baseline and profiling loop.
- DESIGN DECISION for the first CUDA-backed release: use dataset replay on an identified NVIDIA
  host; this laptop remains the CPU comparison machine and live sensor input is deferred. The
  user selected a strict 100 ms per-scan publication deadline with zero
  misses in the accepted window. A complete-path replay benchmark must still be specified
  and passed.
- DESIGN DECISION for the replay release: the complete path must publish each scan within
  100 ms of scheduled arrival, with zero misses in the accepted window. The 10 Hz workload is
  currently a development profile motivated by roughly 104 ms median dataset cadence; its
  final release density/window, overload behavior and resource limits need more decisions.
  A later live safety response requires a vehicle/sensor contract.
- MEASURED RESULT: current headless geometric replay takes 310.3 to 326.9 ms at p50 including
  audit output and sustained 3.05 to 3.21 frames/s for the two 100-frame samples. It cannot sustain the proposed 10 Hz
  workload as implemented. The largest measured stage is `mapping_ms`, not model inference.
