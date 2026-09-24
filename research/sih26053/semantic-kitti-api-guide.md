# Historical SemanticKITTI API research for SIH26053

Archive note: this guide documents an earlier reference adapter, not the current Drishti-2.5 class contract or runtime. The retired project identifier in historical paths was replaced with `legacy-reference`; original paths remain in Git history. For current interfaces, read `docs/interfaces.md` and `Drishti-2.5/src/drishti/semantics.py`.

Checked 21 September 2026 against official API commit `a9c749e8124b2243b6eef1b8bcf971a9f1173a2d`. See the [verification results](/home/ashin/Hackathon/SIH/research/sih26053/evidence/verification.json).

## What this API can and cannot do

[PRBonn/semantic-kitti-api](https://github.com/PRBonn/semantic-kitti-api) is a local Python toolkit, not a hosted REST API. It supplies dataset readers, label definitions, spherical projection, visualizers and benchmark evaluators. It does not download the LiDAR dataset, infer semantics/motion for you, construct an adaptive elevation grid or deskew scans. Here, “GIS” means the user's real-time 2.5D visualization dashboard, not a geographic information system.

Use it as the **format and evaluation reference**, with a small explicit adapter into the historical prototype. Obtain KITTI odometry scans/calibration and SemanticKITTI annotations separately through the [official dataset page](https://www.semantic-kitti.org/dataset.html). For initial work, labeled validation sequence 08 is sufficient to exercise the file pipeline, but tuning and final evaluation must be separated. Training sequences are 00-07, 09 and 10; validation is 08; 11-21 are the benchmark test sequences with hidden semantic ground truth. [Official configuration](https://github.com/PRBonn/semantic-kitti-api/blob/a9c749e8124b2243b6eef1b8bcf971a9f1173a2d/config/semantic-kitti.yaml).

## 1. Dataset contract

```text
dataset/
  sequences/08/
    calib.txt
    poses.txt                 SemanticKITTI annotation/SLAM poses
    velodyne/000000.bin        N x 4 float32: x, y, z, remission
    labels/000000.label        N uint32 packed labels, same point order
  poses/08.txt                optional separate KITTI GT trajectory

predictions/
  sequences/08/predictions/000000.label
```

Raw packed labels contain `semantic_raw = word & 0xFFFF` and `instance_id = word >> 16`. Preserve them before learning-class remapping: a moving car and a static car collapse to the same semantic training class. An instance ID is annotation identity, not predicted velocity. [Official reader](https://github.com/PRBonn/semantic-kitti-api/blob/a9c749e8124b2243b6eef1b8bcf971a9f1173a2d/auxiliary/laserscan.py).

For every frame validate:

- Scan byte length divisible by 16, label/prediction byte length equal to `4*N`.
- Exact sequence/frame-name matching, not just equal numbers of sorted files.
- Finite XYZ, sensible ranges, declared units and valid raw label IDs.
- Identical point order across geometry, labels, predictions and masks. Preserve original indices through filtering or voxelization.
- Monotonic timestamps, matching calibration and an explicitly selected pose source.

Semantic scene-completion voxel files use a different format, including voxel labels and masks. Do not feed those `.label` files to the per-point uint32 loader simply because the extension matches.

## 2. Resolve the class-ID mismatch explicitly

| Meaning | Raw semantic ID | Official learning ID | historical perception ID |
|---|---:|---:|---:|
| Ignored / unlabeled | 0 | 0 | -1 |
| Car | 10 | 1 | 0 |
| Moving car | 252 | 1 | 0, plus a separate moving flag |
| Road | 40 | 9 | 8 |
| Pole | 80 | 18 | 17 |
| Traffic sign | 81 | 19 | 18 |

All **34 raw IDs** in the pinned semantic configuration were checked: `historical_id = official_learning_id - 1`, including official ignored ID 0 becoming -1. Upper instance bits were deliberately set high in the fixture; semantics and motion still decoded correctly.

Keep named conventions at adapter boundaries. Do not pass raw 40 as a packed cell class, or official learning ID 9 to a component expecting the historical prototype's road ID 8. The packed cell byte also contains a vote counter: unpack it before interpreting the candidate.

**Reproduced the historical prototype defect:** the CPU `MapEngine` changes negative semantic IDs to 0, incorrectly storing ignored points as car candidates. The existing cell-level unknown sentinel 31 is a candidate solution, but every consuming class lookup must agree. This research did not modify the reference engine. [Engine source](/home/ashin/Hackathon/SIH/legacy-reference/src/run/engine.py).

## 3. Read and project safely

`LaserScan.open_scan()` reads geometry; `SemLaserScan.open_label()` decodes semantics and instances. Use its original point arrays for mapping. Spherical range projection is an image for perception/visibility, **not** an XY elevation map.

Important tested caveats in the pinned API:

1. **Point index 0 mask defect.** `proj_mask` uses `proj_idx > 0`, while valid point indices start at 0. Our file-level fixture has 34 raw points on one ray; the closest point at index 0 survives projection, yet its mask is zero. In an adapter use a validity mask derived from `proj_idx >= 0` and test it. `do_label_projection()` already uses the nonnegative check. No upstream files were patched.
2. **Projection is many-to-one.** In that fixture, one pixel represents 34 retained original points. Do not discard the original scan merely because the projected image contains one point.
3. **Projection parameters are model-specific.** Match image dimensions and FOV to the checkpoint's preprocessing, not merely the physical sensor spec. The API defaults to 64 x 1024; the historical prototype's own projector/configuration is separate. Do not mix their inverse indices or masks.
4. **Equal-depth ties and out-of-FOV returns need an explicit policy.** The API sorts by depth and clamps image coordinates. Treat nearest ownership as a reference behavior, not a cross-backend determinism guarantee for ties.

[Reader/projection source](https://github.com/PRBonn/semantic-kitti-api/blob/a9c749e8124b2243b6eef1b8bcf971a9f1173a2d/auxiliary/laserscan.py). The historical executable fixture remains in Git history and is not a standalone Drishti command.

## 4. Export predictions in the evaluator's format

Semantic predictions must return to original point order. Convert historical perception IDs to official learning IDs, then apply `learning_map_inv` to obtain canonical raw IDs before writing uint32 words. Unknown maps to raw 0. Leave instance bits zero for semantic-only evaluation.

```python
# pred_vr: one int per ORIGINAL input point; values -1 or 0..18.
# cfg: official semantic-kitti.yaml, loaded with yaml.safe_load.
valid = (pred_vr >= 0) & (pred_vr < 19)
learning_ids = np.where(valid, pred_vr + 1, 0)
inverse = np.array([cfg["learning_map_inv"][i] for i in range(20)], dtype="<u4")
raw_prediction = inverse[learning_ids]
# Write only to a new predictions tree, never the source labels directory.
```

This inverse is not lossless: it cannot recover moving-vs-static or bus-vs-other-vehicle distinctions merged by the learning map. Do not reconstruct motion from semantic-only predictions.

For motion evaluation, the separate MOS config defines learning IDs 0=ignore, 1=static, 2=moving; its inverse emits raw 0, **9** and **251**. Use that convention for binary motion predictions, or supported original raw moving classes. Do not export booleans as raw 0/1: both are ignored by the MOS configuration. [MOS configuration](https://github.com/PRBonn/semantic-kitti-api/blob/a9c749e8124b2243b6eef1b8bcf971a9f1173a2d/config/semantic-kitti-mos.yaml).

## 5. Run the official evaluations

Run from the pinned API checkout, replacing the example dataset/prediction paths. These commands were executed successfully here on a synthetic one-frame fixture using the NumPy backend, not on the real dataset.

```sh
python evaluate_semantics.py --dataset /path/to/dataset --predictions /path/to/predictions --split valid --backend numpy

python evaluate_semantics_by_distance.py --dataset /path/to/dataset --predictions /path/to/predictions --split valid --backend numpy

python evaluate_mos.py --dataset /path/to/dataset --predictions /path/to/mos-predictions --split valid --backend numpy --datacfg config/semantic-kitti-mos.yaml
```

Positive control: correct predictions covering all 19 semantic classes yielded approximately **100% mIoU**. Reversing point prediction order, without changing file length, yielded **0%**. Correct synthetic MOS output yielded **100% moving IoU**. These establish interface/evaluator behavior, not model quality. [Semantic log](/home/ashin/Hackathon/SIH/research/sih26053/evidence/api-semantic-perfect.txt), [negative control](/home/ashin/Hackathon/SIH/research/sih26053/evidence/api-semantic-wrong-order.txt), [MOS log](/home/ashin/Hackathon/SIH/research/sih26053/evidence/api-mos-perfect.txt).

Two metric traps:

- **mIoU denominator:** the official implementation averages all included classes, including classes absent from a small evaluated subset. A perfect one-class fixture gives `1/19 = 5.263%`, not 100%. The historical prototype's documented 65.2% over 200 frames uses present classes and cannot be directly compared with the official benchmark figure. Report full official mIoU and optional present-class mIoU under distinct names. [Evaluator source](https://github.com/PRBonn/semantic-kitti-api/blob/a9c749e8124b2243b6eef1b8bcf971a9f1173a2d/auxiliary/np_ioueval.py).
- **Distance bins:** the official distance script uses 3D Euclidean range and open intervals ending at 50 m. Exact distances 10, 20, 30, 40 and 50 m belong to no bin in the pinned code; this was reproduced. Keep its output for comparison, but add a separately named evaluator with exhaustive half-open bins and a 50-100 m bin for this problem. Also report actual adaptive ring membership, which is not the same as Euclidean range. [Distance source](https://github.com/PRBonn/semantic-kitti-api/blob/a9c749e8124b2243b6eef1b8bcf971a9f1173a2d/evaluate_semantics_by_distance.py).

Never omit failed/unprojected points to inflate the per-point score. If the mapper cannot assign a prediction, retain the point with an explicit unknown prediction and report coverage. A point-semantic score does not measure height error, negative obstacles, clearance or displayed map alignment.

## 6. Other useful API tools and cautions

| Tool | Useful role | Limitation / safe usage |
|---|---|---|
| `visualize.py`, `compare.py` | Inspect scans, annotations and predictions | Optional display dependencies; not executed here. Correct colors do not establish geometry correctness. |
| `generate_sequential.py` | Build temporally aggregated clouds using poses | Transforms historical scans into the current frame; not intra-scan deskew or object-motion compensation. Moving-object trails remain possible. Use a new output tree. |
| `remap_semantic_labels.py` | Convert raw and learning semantic IDs | **Writes label files in place.** Avoid on original data. Map in memory or on a recoverable copy; forward/inverse mapping cannot restore collapsed motion classes. |
| `evaluate_panoptic.py` | Evaluate semantics plus instances | Only relevant when the model predicts instances; GT instance IDs are not a model's detections. |
| `evaluate_completion.py` | Evaluate voxel scene completion | Separate task/format, not elevation-map accuracy. |
| `validate_submission.py` | Submission structure checks | Add independent frame-ID, point-count and label-domain checks; do not treat structure validation as accuracy evidence. |

These rows are code/documentation inspection, not claims that every listed tool was executed. [Sequential generator](https://github.com/PRBonn/semantic-kitti-api/blob/a9c749e8124b2243b6eef1b8bcf971a9f1173a2d/generate_sequential.py), [in-place remapper](https://github.com/PRBonn/semantic-kitti-api/blob/a9c749e8124b2243b6eef1b8bcf971a9f1173a2d/remap_semantic_labels.py).

## 7. How to connect it to the real-time 2.5D dashboard

Maintain two explicitly separate experiments:

1. **Mapping-only diagnostic:** annotated semantics/motion and a pinned pose source enter the grid. This isolates projection, compression and state-management losses. Results are oracle-input results.
2. **End-to-end perception:** only sensor data and the declared localization inputs enter the pipeline; model-predicted semantics/motion drive the map. Ground-truth labels are read solely by evaluation. Masking labels must not alter predictions.

Use official point-level metrics for semantics/MOS, then add grid/display measurements: height/clearance error, valid coverage, seam artifacts, thin-object and pothole recall, false-free space, ghost lifetime, displayed-data age and rendering FPS. SemanticKITTI's road label is not a vehicle-specific ground-truth drivability label, and this driving dataset alone does not establish performance on unseen terrain, weather or different sensors.

The recommended pipeline is original scans and timing -> declared motion compensation/pose transform -> predicted semantics and motion -> raw-point-index-preserving grid adapter -> actual 2.5D cells -> dashboard geometry/colors and timing/memory panels. Store annotations in the evaluation branch, not the production feature branch. Use the official color map only after explicitly converting IDs and confirming its BGR/RGB convention; color the cell's semantic candidate, not its packed class-and-counter byte. A raw-cloud visualizer alone does not satisfy the adaptive-map dashboard requirement.

The dashboard comparison must include uniform high-resolution **3D** storage, with the same declared volume and resolution. Separate theoretical dense voxel bytes, actually allocated grid bytes, occupied payload and full process/GPU memory. Do not label a uniform-2D comparison or occupied-cell count as the requested 3D memory measurement.

Full bottleneck decisions: [verified solutions report](/home/ashin/Hackathon/SIH/research/sih26053/verified-solutions.md).
