# Test rules

Read the root and package `AGENTS.md`. For a bug, first reproduce the user-visible failure via
CLI or replay where feasible, then add the smallest meaningful regression test. Use fixtures
that exercise real contracts: point ordering, unknown labels, pose/time, accounting conservation,
projection losers, sequence reset, and immutable snapshots.

Keep oracle-label tests separate from production behavior. Do not replace native processing with
mocks and claim integration coverage. Mark optional viewer behavior explicitly. Never remove or
skip a failing test to satisfy a gate; explain unavailable data or hardware as NOT VERIFIED.
