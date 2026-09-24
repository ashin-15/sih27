# Experiment record template

Create one `EXP-YYYY-NNN-short-name.md` per model evaluation, dataset trial, benchmark or simulation. Do not prefill observed results. Link an execution task and research question.

```markdown
# EXP-YYYY-NNN - <name>

Status: Planned | Running | Completed | Failed
Research question:
Objective:
Hypothesis:
Setup and environment:
Inputs and dataset split:
Configuration and checkpoint hashes:
Baseline:
Metrics and acceptance thresholds:
Expected outcome:
Observed outcome: NOT VERIFIED until run
Interpretation:
Limitations:
Reproduction commands:
Conclusion:
Next action:
```

Save machine-readable outputs outside the source dataset, with hashes and a path in the record. Preserve failed runs and distinguish snapshot array bytes, process RSS, model memory and viewer memory.
