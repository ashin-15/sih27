# Model candidate screen

Updated 2026-09-27. D-002 approved FRNet for a bounded semantic-only CPU slice;
D-005 numeric quality gates remain open. The local checkpoint is hash-pinned,
and E-050 records one real Drishti replay from source and an installed wheel.

| Candidate | Evidence and plausible role | Contract gaps to test | Status |
| --- | --- | --- | --- |
| Current geometric path | Code inspection: produces ground and single-frame cells, with semantic ID 0 in production mode. It is the reproducible no-model baseline. | No learned class, instance, motion, track, or visibility output. | Existing baseline |
| FRNet / Fast-FRNet | [Authors' repository](https://github.com/Xiangxu-0103/FRNet) links SemanticKITTI checkpoints and an Apache-2.0 project license. The local checkpoint is hash-pinned in [screen 0022](experiments/0022-local-frnet-checkpoint-screen.md); E-049 verified isolated original-point inference. E-050 verified Drishti CPU replay with the explicit 0..18 to 1..19 and ignore 19 to unknown 0 remap. | Confirm exact upstream-byte identity and separate weight terms. Evaluate complete sequence 08, per-class/range coverage and resource use against approved numeric gates; CUDA/release latency is separate. Published network FPS is not capture-to-map latency. | Approved D-002 semantic CPU slice implemented; T-003 quality validation IN PROGRESS |
| Autoware FRNet integration and artifacts | [Maintainer documentation](https://github.com/autowarefoundation/autoware_universe/blob/main/perception/autoware_lidar_frnet/README.md) describes TensorRT stage timings. Its [artifact card](https://huggingface.co/AutowareFoundation/lidar_frnet/commit/a53a1c11b0b28d31fd50a03abef5db0e830a5b3c) supplies sensor-specific ONNX models trained on T4Dataset with 27 classes. | Drishti uses SemanticKITTI IDs 0 through 19; these weights are not a direct class-contract match. They also require compatible sensor preprocessing and accelerator. See [screen 0020](experiments/0020-frnet-artifact-screen.md). | Instrumentation reference; reject as drop-in SemanticKITTI checkpoint |

## Remaining T-003 acceptance gates

1. D-002 selected the CPU semantic slice, class/unknown rules and sequence 08 validation split.
   Approve numeric D-005 acceptance gates before T-003 closure.
2. Record repository revision, code license, checkpoint source and terms, immutable checkpoint
   hash, framework versions, exact input normalization, point projection/scatter, and class map.
   Local checkpoint/export hashes and source revision are recorded in experiment 0024;
   exact public-byte identity and separate weight terms remain open.
3. E-050 and adapter fixtures cover accepted original point IDs, pixel collisions, invalid
   intensity, ROI rejection, missing classes and unknown points. Broader data coverage remains open.
4. Run the [official evaluator](https://github.com/PRBonn/semantic-kitti-api) on held-out data
   and save per-class and range results. Keep prediction files outside the source dataset.
5. Measure preprocess, inference, postprocess, queue wait, map update, publication, and process
   memory together. Compare against the same-path geometric and oracle controls without using
   oracle labels in prediction.

FRNet alone cannot satisfy detection, tracking, measured motion, or free-space criteria. The
[SemanticKITTI task definitions](https://semantic-kitti.org/tasks.html) score point semantics,
panoptic instances, 4D association, and moving points as distinct tasks. Drishti also needs
separate obstacle and visibility evidence beyond any one benchmark score.
