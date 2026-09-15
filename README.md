# SIH26053 Adaptive 2.5D LiDAR Mapping

Phase 1 establishes a reproducible Kaggle development environment for the official SIH26053 problem. It validates the selected nuScenes-mini mirror and point-wise lidarseg contract before adaptive-grid or model work begins.

## Dataset

Use only:

- `vyomkeshsharma/nuscenes-mini-complete-with-lidarseg`
- nuScenes metadata version `v1.0-mini`
- label files under `lidarseg/v1.0-mini`

The mirror also contains `lidarseg/v1.0-trainval`; Phase 1 explicitly counts and excludes those files.

## Local environment

The local `.venv` is only for Kaggle CLI and repository/tooling tasks. Scientific and GPU dependencies are provided by Kaggle.

```bash
./.venv/bin/kaggle --version
```

## Kaggle prerequisites

Create an empty private GitHub repository and provide its clean HTTPS URL. Create a fine-grained token restricted to that repository with `Contents: Read-only`.

Attach these Kaggle Secrets to the private notebook:

- `FOVEAMAP_REPO_URL` — clean HTTPS repository URL, without credentials
- `GITHUB_READ_TOKEN` — fine-grained read-only token

Do not commit credentials or place them in the Git remote.

## Kaggle execution

`kaggle/kernel-metadata.json` requests Internet and GPU and attaches the selected dataset. The notebook can be pushed with the project-local CLI after the repository remote and notebook slug are finalized:

```bash
./.venv/bin/kaggle kernels push -p kaggle
```

Kaggle Secrets are attached through the notebook UI/API rather than committed to metadata.

## Phase 1 outputs

A clean Kaggle run writes under `/kaggle/working/artifacts/phase1/`:

- `environment.json`
- `dataset_audit.json`
- `sample_summary.json`
- `sample_height_bev.png`
- `sample_semantic_bev.png`
- `phase1_summary.json`

The phase passes only if the complete mini audit validates all expected scene, sample, keyframe, lidarseg, point/label-count, and label-index contracts.
