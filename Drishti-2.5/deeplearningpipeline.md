# Deep-learning pipeline for vehicle deployment

**Status: proposed architecture, not implemented or safety-qualified.** Drishti-2.5 is currently a single-frame, CPU-first elevation mapper. This document describes how to extend it for a moving vehicle without making immediate obstacle response depend on a neural network. The operating speed, sensing range, deadlines, and fallback behavior must be validated on the actual vehicle and compute hardware.

## What the current measurements say

Fresh [sequence 00](runs/drishti-hardware-baseline-20260924-seq00-100/summary.json) and [sequence 08](runs/drishti-hardware-baseline-20260924-seq08-100/summary.json) headless SemanticKITTI replays each completed 100 frames on the current Core Ultra 9 185H host. Audit-inclusive median latency was 310.3 and 326.9 ms respectively, with 100/100 misses of the configured 100 ms budget in each run. Steady processing p50 was 260.2 and 271.2 ms; median `mapping_ms` from the [sequence 00 frames](runs/drishti-hardware-baseline-20260924-seq00-100/frames.jsonl) and [sequence 08 frames](runs/drishti-hardware-baseline-20260924-seq08-100/frames.jsonl) was 170.3 and 179.8 ms. These are replay measurements without model, temporal state, viewer or vehicle input-to-actuation timing. They show that an accelerator for FRNet alone will not resolve the present CPU mapping bottleneck. Both manifests explicitly list no temporal fusion, no motion estimation, unavailable deskew, and no real-time claim.

`MappingEngine.process` currently performs filtering, Patchwork++ ground extraction, diagnostic range projection, and cell aggregation in sequence. Geometric mode has no learned semantic labels; oracle mode uses dataset annotations, which are unavailable on a vehicle. Its snapshots cover one scan, not a persistent occupancy map. The range-image projection retains only a winner per pixel, while map aggregation uses all accepted points. Neither a `ground_valid` cell nor the absence of a return establishes free space or a traversable route. See [pipeline.py](src/drishti/pipeline.py), [mapping.py](src/drishti/mapping.py), and [AGENTS.md](AGENTS.md).

## Proposed processing paths

```text
Timestamped LiDAR packets/scan + per-point timing + pose/IMU
  |
  +--> deskew, calibration, scan ID and original point IDs
         |
         +--> EVERY SCAN: bounded-cost geometric obstacle evidence
         |       --> ego-motion-compensated local occupancy/obstacle memory
         |       --> planner + independent control / stop watchdog
         |
         +--> detailed Drishti elevation snapshot when its deadline permits
         |       --> richer terrain evidence for planning
         |
         +--> OPTIONAL: FRNet inference on an accelerator
                 --> point-aligned, timestamped class probabilities
                 --> fuse only while fresh and geometrically consistent
```

The every-scan safety path must finish within a defined deadline and retain near-field obstacle evidence even if the full elevation snapshot or FRNet misses its deadline. It can be a simpler geometric update than the complete current snapshot, but must still enforce calibrated ranges, coordinate transforms, point accounting, and conservative treatment of invalid/unknown observations. The planner and controller should run at their own validated rates; neither should block waiting for GPU inference, visualization, or disk I/O. A fast path is a proposal to be built and tested, not an existing Drishti feature.

### Preserve observations without an unbounded queue

- **Do not silently discard an unprocessed scan on the only obstacle-detection path.** A small obstacle may be visible once and then become occluded. Ingest each scan's safety-relevant geometry promptly into a persistent, bounded local map before it is eligible for any optional work-skipping policy. If even that path cannot keep up, raise a deadline fault and slow/stop under the validated fallback policy; an ever-growing FIFO is not a safe substitute for throughput.
- **Persist evidence, not just a last-frame map.** Transform observations to a common frame with synchronized pose; retain occupied/unknown state, observation timestamps, and confidence. Track potentially moving objects separately and predict conservatively during short occlusions. Expire old evidence by a tested policy; clear occupancy only using valid, unobstructed, positively observed free-space rays where the sensor model supports that inference. An absent return or an occluded region is not free. The current elevation map does not implement ray-based free space.
- **A bounded latest-only queue is appropriate for optional FRNet jobs after geometry has been ingested.** Dropping an older *unstarted semantic job* loses its label, not its geometric obstacle evidence. If a particular decision requires an unavailable label, apply the defined conservative policy rather than guessing it. Associate results with their original scan ID, point IDs, capture time, pose, and model version; discard labels that are stale or no longer associate correctly. Never overwrite a newer geometric state with an older semantic result.
- **Keep collision and rejection accounting.** Map accepted spatial points regardless of range-image pixel collisions, and monitor invalid geometry, points outside the configured ROI, missing intensity, dropped work, and stale results. Filtering a point outside the ROI is a deliberate coverage limit, not proof that the area is clear.

### Where FRNet fits

FRNet provides **semantic segmentation**, not braking logic, motion estimation, or proof of traversability. Its point-wise output should be remapped to the original sensor-frame points, then to Drishti's canonical SemanticKITTI learning IDs (0 unknown, 1 car, etc.) as appropriate for the deployed model. Do not treat the current diagnostic `RangeImage` winners as the complete set of mapping points; preserve original IDs for non-winners too. Predicted probabilities and calibration matter: low-confidence or unmatched points remain unknown. A separate temporal tracker is required for motion; the `motion` field in oracle mode is derived from ground-truth labels, not inferred by the present geometric pipeline.

Run FRNet asynchronously only if its classes materially improve planning on the target operating domain. The [official FRNet benchmarks](https://github.com/Xiangxu-0103/FRNet) report model throughput under their test conditions, not vehicle capture-to-actuation latency. [Autoware's FRNet package](https://github.com/autowarefoundation/autoware_universe/blob/main/perception/autoware_lidar_frnet/README.md) is a TensorRT integration reference and separates preprocessing, inference, postprocessing, and pipeline latency. Sensor origin, field of view, resolution, return format, and class taxonomy must be checked against training data; pretrained performance cannot be assumed to transfer to a different LiDAR or environment. If using FP16/INT8, smaller models, ROI inference, or fewer semantic updates, re-evaluate critical-class recall and tail latency, especially for near-field pedestrians and small obstacles.

## Latency work in priority order

1. **Measure on target hardware before redesigning.** Record acquisition/packet assembly, deskew and pose lookup, filtering, ground extraction, projection, mapping sub-operations, copies, publication, queue wait, inference transfer/compute/postprocessing, planner consumption, and actuation. Report processing throughput separately from age of information at the planner; overlapping tasks can improve throughput without reducing an individual result's latency.
2. **Profile and optimize mapping first.** The replay points to `mapping_ms` as the dominant measured stage. Profile `resolve_owners`, key sorting/`np.unique`, repeated indexed reductions, semantic histograms, and memory allocations separately before choosing an optimization. Avoid calculating full semantic evidence on a geometry-only critical path when it has no labels. Consider bounded, preallocated rolling-grid or compiled CPU kernels only after profiling; preserve the lattice ownership rules, fixed-point overflow guarantees, immutable publication contract, and accounting tests. `immutable()` currently calls `tobytes()`, so its read-only result involves a buffer copy: measure those copies rather than assuming zero-copy publication.
3. **Remove optional work from the critical deadline.** The current projection is diagnostic, not a prerequisite for spatial cell aggregation. Move diagnostic projection, visualization, hashing, and audit writes to bounded lower-priority consumers where possible, while retaining sufficient metadata to audit what was ingested and what was skipped. Measure any new queueing and memory costs.
4. **Limit computation by safety relevance, not arbitrary data loss.** Preserve the sensor coverage and near-field resolution needed for stopping, and use coarser or less frequent enriched representations where measured to be acceptable. Any change to point filtering, ROI, or update frequency requires obstacle-recall and latency tests, including thin, low-reflectivity, temporarily occluded, and fast-moving objects.
5. **Then size the semantic accelerator.** Measure the complete FRNet path on target hardware under simultaneous mapping/planning load. Choose the model, precision, and update rate by critical-class accuracy and worst-case resource contention, not network FPS alone.

For a sensor producing one scan every 100 ms, a path taking 280 ms per scan cannot process every scan indefinitely; parallelism only helps if sustained throughput exceeds input rate and queues remain bounded. At the same time, dropping scans before the safety path risks losing unique evidence. The correct response is to reduce the mandatory work, retain its observations across time, and fault safely if its deadline is missed.

## CPU or GPU?

| Requirement | Compute choice | Decision condition |
| --- | --- | --- |
| Immediate geometric obstacle evidence | CPU first, possibly compiled/optimized | Demonstrate bounded every-scan throughput and capture-to-planner latency on the actual compute platform; the present replay does not meet its 100 ms target. |
| Detailed elevation snapshot | CPU if optimized sufficiently; lower-priority scheduling if not | Must not delay the immediate safety path. GPU porting is an option only if profiling and integration tests justify it. |
| FRNet semantic classes | Typically an onboard GPU or other supported inference accelerator | Needed only if semantic classes are required and measured CPU inference cannot meet freshness, accuracy, and power limits. An accelerator does not fix slow CPU mapping. |

A CPU-only **geometric** prototype is plausible, but the current code is not a demonstrated real-time vehicle implementation. A GPU is **not intrinsically required by Drishti's geometry**. If FRNet is a required component, plan for an appropriate accelerator unless target-hardware measurements establish a viable alternative. In either case, retain a geometry-driven response to missing, stale, or failed inference.

## Acceptance criteria to define before deployment

- Specify the sensor rate, operating speed/domain, reliable detection range, braking capability, localization quality, compute/power budget, maximum acceptable age of obstacle evidence, and fault response. Check stopping distance using at least `v * measured perception-to-actuation delay + v^2 / (2 * available deceleration) + safety margin`, with delay and deceleration justified under adverse conditions. A p99 alone is not a hard safety bound: test deadline misses and define the response to them.
- Measure sustained throughput, p50/p95/p99 and worst-observed stage and capture-to-actuation latency, queue depth, dropped optional jobs, GPU contention, memory, and thermal throttling on target hardware. Include scan acquisition time rather than timing only after a full scan arrives.
- Test synchronized timestamps, motion deskew, pose uncertainty, frame transformations, rolling-map ageing, occlusion, dynamic objects, sensor failures, GPU stalls, and delayed/out-of-order semantic results. Verify that unknown/ambiguous cells never become unearned free-space or passability claims.
- Compare optimized geometry and any accelerated inference with baseline accounting, ownership-seam tests, obstacle recall, critical-class recall, and replay evidence. Exercise prolonged overload and verify the speed restriction/stop watchdog. Integrate and validate with the vehicle planner and control system before any on-road use.
