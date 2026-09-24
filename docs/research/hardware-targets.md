# Hardware target screen

Updated 2026-09-24. The current machine is the development target selected for the first replay
and optimization cycle. No new hardware purchase is required for that cycle. The model and
deployment targets remain research candidates, not approved release hardware.

| Role | Candidate | Evidence and decision condition |
| --- | --- | --- |
| Current development baseline | Intel Core Ultra 9 185H, 22 logical CPUs, integrated Intel Arc graphics and NPU, 30 GiB RAM, Linux x86_64. | Local `lscpu`, `lspci` and `free -h`; 200 real replay frames in experiment 0001. Suitable for current CPU-first tests and profiling, but the existing path missed 100 ms on every measured frame. Integrated accelerator inference is NOT VERIFIED. |
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
- HYPOTHESIS for engineering: a future complete path should publish each scan within 100 ms of
  capture and sustain at least 10 Hz without unbounded queue growth. This is motivated by the
  measured roughly 104 ms dataset cadence, not by achieved performance. A release deadline,
  miss policy and safety response require a vehicle/sensor contract and longer target tests.
- MEASURED RESULT: current headless geometric replay takes 310.3 to 326.9 ms at p50 including
  audit output and sustained 3.05 to 3.21 frames/s for the two 100-frame samples. It cannot sustain the proposed 10 Hz
  workload as implemented. The largest measured stage is `mapping_ms`, not model inference.
