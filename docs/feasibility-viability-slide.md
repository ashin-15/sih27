# Drishti-2.5 feasibility and viability: pitch evidence

Reviewed 2026-09-29. Presentation support only; no new implementation approval.

## Claim boundaries

- FACT: the shared replay path integrates Patchwork++, FRNet and adaptive cell mapping.
  See `project-assessment.md`, `../Drishti-2.5/src/drishti/pipeline.py` and
  `research/experiments/0026-t003-cpu-semantic-verification.md`.
- MEASURED RESULT: E-051 reports semantic mIoU 0.6754690443 across 4,071
  SemanticKITTI sequence 08 scans and 19 classes. Saved predictions span a
  793-scan prefix and a new-engine continuation. This is point-semantic evidence,
  not continuous-state or field-safety evidence.
- FACT: local CPU replay uses provisioned models, dependencies and dataset files.
  No mandatory cloud inference API is in the active runtime. Local computation
  is not proof of field robustness, security or real-time embedded suitability.
- MEASURED RESULT: E-052 reports model-stage p50 7,177 ms and whole-engine p50
  7,283 ms. The 100 ms complete-product gate remains NOT VERIFIED.
- PROPOSAL: a ROS 2 PointCloud2 adapter is one future integration route, not an
  existing Drishti interface. Calibration, synchronization, live ingestion,
  output semantics and target hardware tests must precede vehicle deployment.
- FACT: dependency locks, checkpoint/source pinning and automated tests exist.
  Their value is traceable upgrades; long-term staffing, support and release
  ownership remain UNKNOWN.
- UNKNOWN: deployment cost, recurring support cost and commercial checkpoint
  permissions. Public software availability does not establish zero-cost deployment.

## Primary sources inspected on 2026-09-29

- Patchwork++ authors, IROS 2022 paper and current repository:
  https://arxiv.org/abs/2207.11919
  https://github.com/url-kaist/patchwork-plusplus
  Supports established ground segmentation and available Python/C++ interfaces.
- FRNet authors, TIP 2025 project repository:
  https://github.com/Xiangxu-0103/FRNet
  Supports available LiDAR semantic segmentation code, model links and a declared
  Apache-2.0 code license. Upstream FPS is not Drishti performance.
- SemanticKITTI official dataset documentation:
  https://semantic-kitti.org/dataset.html
  Provides annotated driving sequences and explicitly states a noncommercial
  dataset license. Dataset/model rights require separate review before deployment.
- ROS 2 official message source:
  https://raw.githubusercontent.com/ros2/common_interfaces/rolling/sensor_msgs/msg/PointCloud2.msg
  Provides fields, acquisition timestamp and coordinate-frame metadata, supporting
  a proposed adapter. It does not supply Drishti calibration or integration.
- DRDO official UGV technology foresight:
  https://drdo.gov.in/drdo/en/offerings/technology-foresight/ugv
  Lists AI perception/navigation and algorithm validation as technology tasks.
  Establishes application relevance, not endorsement, procurement or funding.

## Recommended slide story

Five sections: technical foundation, local operation, economic viability,
vehicle integration, maintainable upgrades. Each uses a short hook, two
supporting statements and explicit Proven/Proposed/Test or Validate labels.
Put build, operate and afford across the top; integrate and maintain below.
Keep detailed references and timing/licensing explanation in speaker notes.
