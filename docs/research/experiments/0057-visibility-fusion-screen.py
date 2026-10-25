"""Compare full visibility evidence with the saved pre-fusion CUDA implementation.

Run from Drishti-2.5, passing normal replay CLI arguments. The immutable source
snapshot is artifacts/workflow-reference-20261022/visibility.py. Duplicate
computation makes CLI timing instrumented, not a release benchmark.
"""

import ast
import json
import sys
from dataclasses import fields
from pathlib import Path
from time import perf_counter
from types import MethodType

import numpy as np

from drishti import visibility
from drishti.cli import main

reference = Path("../artifacts/workflow-reference-20261022/visibility.py")
tree = ast.parse(reference.read_text(encoding="utf-8"))
cls = next(
    n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "CurrentScanVisibility"
)
scope = dict(vars(visibility))
for name in ("compute", "_corridor_pairs"):
    node = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(reference), "exec"), scope)
current = visibility.CurrentScanVisibility.compute
reports = []


def compare(self, *args, **kwargs):
    start = perf_counter()
    candidate = current(self, *args, **kwargs)
    candidate_ms = (perf_counter() - start) * 1000
    pairs = self._corridor_pairs
    self._corridor_pairs = MethodType(scope["_corridor_pairs"], self)
    try:
        start = perf_counter()
        expected = scope["compute"](self, *args, **kwargs)
        reference_ms = (perf_counter() - start) * 1000
    finally:
        self._corridor_pairs = pairs
    for field in fields(expected):
        left, right = getattr(expected, field.name), getattr(candidate, field.name)
        if isinstance(left, np.ndarray):
            assert left.tobytes() == right.tobytes(), field.name
        else:
            assert left == right, field.name
    reports.append(
        {
            "candidate_ms": candidate_ms,
            "reference_ms": reference_ms,
            "free_cells": candidate.summary.free_cells,
            "full_byte_parity": True,
        }
    )
    return candidate


visibility.CurrentScanVisibility.compute = compare
result = main(sys.argv[1:])
output = Path(sys.argv[sys.argv.index("--output") + 1])
(output / "visibility-parity.json").write_text(json.dumps(reports, indent=2), encoding="utf-8")
print(f"Full visibility byte parity: {len(reports)} frames; CLI status {result}")
if not reports or result not in (0, 2):
    raise SystemExit(1)
