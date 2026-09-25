# Model candidate screen

Updated 2026-09-25. This is a research screen, not a model selection. D-001, D-002, and D-005
remain open. No candidate has been downloaded, run, or measured in Drishti.

| Candidate | Evidence and plausible role | Contract gaps to test | Status |
| --- | --- | --- | --- |
| Current geometric path | Code inspection: produces ground and single-frame cells, with semantic ID 0 in production mode. It is the reproducible no-model baseline. | No learned class, instance, motion, track, or visibility output. | Existing baseline |
| FRNet / Fast-FRNet | [Authors' repository](https://github.com/Xiangxu-0103/FRNet) links SemanticKITTI checkpoints, an Apache-2.0 code license, and segmentation results under its own test conditions. Candidate for point semantics only. | This review could not inspect the shared folder's exact files, separate weight terms or hashes in [screen 0020](experiments/0020-frnet-artifact-screen.md). Verify preprocessing, class map, all-point alignment, unknown handling, memory and full Drishti latency. Published network FPS is not capture-to-map latency. | Research candidate; exact checkpoint NOT VERIFIED |
| Autoware FRNet integration and artifacts | [Maintainer documentation](https://github.com/autowarefoundation/autoware_universe/blob/main/perception/autoware_lidar_frnet/README.md) describes TensorRT stage timings. Its [artifact card](https://huggingface.co/AutowareFoundation/lidar_frnet/commit/a53a1c11b0b28d31fd50a03abef5db0e830a5b3c) supplies sensor-specific ONNX models trained on T4Dataset with 27 classes. | Drishti uses SemanticKITTI IDs 0 through 19; these weights are not a direct class-contract match. They also require compatible sensor preprocessing and accelerator. See [screen 0020](experiments/0020-frnet-artifact-screen.md). | Instrumentation reference; reject as drop-in SemanticKITTI checkpoint |

## Candidate gate before adapter work

1. Freeze target hardware, first model milestone, class/unknown rules, held-out split, and numeric
   acceptance gates in the product contract.
2. Record repository revision, code license, checkpoint source and terms, immutable checkpoint
   hash, framework versions, exact input normalization, point projection/scatter, and class map.
3. Test the adapter on reordered points, pixel collisions, invalid intensity, ROI rejection,
   missing classes, and unknown points. The output must align to accepted original point IDs.
4. Run the [official evaluator](https://github.com/PRBonn/semantic-kitti-api) on held-out data
   and save per-class and range results. Keep prediction files outside the source dataset.
5. Measure preprocess, inference, postprocess, queue wait, map update, publication, and process
   memory together. Compare against the same-path geometric and oracle controls without using
   oracle labels in prediction.

FRNet alone cannot satisfy detection, tracking, measured motion, or free-space criteria. The
[SemanticKITTI task definitions](https://semantic-kitti.org/tasks.html) score point semantics,
panoptic instances, 4D association, and moving points as distinct tasks. Drishti also needs
separate obstacle and visibility evidence beyond any one benchmark score.
