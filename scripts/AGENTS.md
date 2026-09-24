# Dataset utility rules

Read the root `AGENTS.md`. The dataset validator is a read-only inspection tool. Never alter
scan, label, pose, calibration, or timestamp files. Keep report paths explicit and new; preserve
per-sequence coverage and failure details. A smoke replay or partial report is not full-dataset
validation. Test CLI parsing and report status after validator changes.
