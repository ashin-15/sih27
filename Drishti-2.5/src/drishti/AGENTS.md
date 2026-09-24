# Runtime source rules

Read the root and package `AGENTS.md`, plus `docs/interfaces.md`, before editing runtime code.
The CLI, replay, synthetic path, and optional viewer must share `MappingEngine.process` and the
same contracts. Keep one engine per sequence; Patchwork++ state is sequence-specific.

- Preserve original point alignment and unique nonnegative int64 IDs through filtering and
  projection. Mapping uses every accepted spatial point, including projection losers.
- Keep SemanticKITTI learning ID 0 unknown. Oracle labels are evaluation input only; production
  inference must never silently consume them.
- Keep frames, timestamps, poses, transforms, and output arrays validated and immutable.
- Ground spread and height envelopes are descriptive. Never expose them as free-space,
  clearance, passability, calibrated uncertainty, or object evidence without new proof.
- New temporal or model state must have an explicit sequence reset and bounded memory contract.
  Record material interface changes and test same-path CLI behavior.
- Run focused tests, Ruff, mypy, and the relevant broader suite before reporting verification.
