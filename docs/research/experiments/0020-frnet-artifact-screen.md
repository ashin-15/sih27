# Experiment 0020: FRNet artifact and class-contract screen

Status: FACT from primary project/model records and UNKNOWN for an exact
deployable SemanticKITTI checkpoint, reviewed 2026-09-25. RQ-001/RQ-004,
O-001/O-002/T-003. This is source review, not a downloaded or executed model.

## Sources and method

- The [FRNet authors' repository](https://github.com/Xiangxu-0103/FRNet/blob/master/README.md)
  links pretrained SemanticKITTI and nuScenes weights through a shared Google
  Drive folder and describes the project as Apache-2.0 licensed. The
  [repository LICENSE](https://github.com/Xiangxu-0103/FRNet/blob/master/LICENSE)
  contains Apache-2.0 text. The accessible Drive page did not expose an
  inspectable file list, separate checkpoint terms, or immutable file hashes
  through this review path.
- The [Autoware Foundation FRNet artifact card](https://huggingface.co/AutowareFoundation/lidar_frnet/commit/a53a1c11b0b28d31fd50a03abef5db0e830a5b3c)
  identifies ONNX weights exported for its ROS 2/TensorRT node. It lists 27
  classes, HESAI OT128/QT128 sensor variants, and training on T4Dataset.
  The two ONNX LFS objects at that commit have recorded SHA-256 values, but
  they are not the authors' SemanticKITTI checkpoints.
- The [authors' installation guide](https://github.com/Xiangxu-0103/FRNet/blob/master/docs/INSTALL.md)
  reports testing with Python 3.8, PyTorch 1.8.1, MMDetection3D and CUDA
  10.2/11.1. That is a tested environment, not proof that other runtimes
  cannot work.
- The current [Drishti semantic contract](../../../Drishti-2.5/src/drishti/semantics.py)
  uses SemanticKITTI learning IDs 0 through 19, with 0 unknown/ignored.
  The [dataset source](../../../Drishti-2.5/src/drishti/dataset.py) supplies
  SemanticKITTI points and SLAM poses for replay. No model adapter is present.

The installed `hf` CLI is version 1.31.0. A read-only Hub query failed with
DNS resolution unavailable in this sandbox. A local cache search returned no
FRNet entry; this does not establish that no suitable Hub model exists. No
checkpoint was downloaded, executed, or introduced into the source tree.
On the selected laptop, `lspci` showed Intel Arc integrated graphics and the
Drishti environment reported Python 3.12.14 with no `torch` installed. No
FRNet CUDA, Intel GPU, NPU or CPU execution was tested.

## Contract judgment

FACT: the Autoware artifacts cannot be treated as a direct SemanticKITTI
learning-ID checkpoint. Their 27-class T4Dataset output and sensor-specific
preprocessing require an explicit class remap or retraining decision, plus
point alignment and accuracy validation. Apache-2.0 on that model card does
not establish the terms of the authors' separately hosted weights.

UNKNOWN: the exact files, hashes, separately applicable terms, preprocessing
revision and target-laptop runtime of the authors' SemanticKITTI checkpoints.
The authors' documented Python/CUDA stack is not a direct match for this
laptop's current Drishti environment; a port or separately compatible model
backend would need its own correctness and latency evidence.
The authors' reported model FPS is not a measured Drishti capture-to-complete-
output age. Keep FRNet as a research candidate only. Before adapter work,
obtain and pin an allowed checkpoint, inspect its class map and preprocessing,
then freeze the model milestone and acceptance gate under D-002/D-005.
