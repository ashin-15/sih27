# Preset rules

Read the root and package `AGENTS.md`. Presets must use the strict loader in `src/drishti/config.py`.
Keep paths relative to the preset where applicable, declare pose sources explicitly, and reject
unknown fields. Never embed private local dataset paths, credentials, or output artifacts.
When changing a preset or schema, check its parsed values, overflow constraints, and focused
configuration tests. A configured latency budget is not a measured guarantee.
