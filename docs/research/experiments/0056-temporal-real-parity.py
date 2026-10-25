"""Run the real CLI with a same-state CPU check of every fused array.

Pass normal CLI arguments. Instrumented timing is not a performance result.
"""

import sys
from dataclasses import fields

import numpy as np

from drishti.cli import main
from drishti.temporal import TemporalMap

original = TemporalMap._view
checked = 0


def compare(self, *args, **kwargs):
    global checked
    candidate = original(self, *args, **kwargs)
    workspace = self._cuda_steps
    assert workspace is not None
    self._cuda_steps = None
    try:
        reference = original(self, *args, **kwargs)
    finally:
        self._cuda_steps = workspace
    for field in fields(reference):
        left, right = getattr(reference, field.name), getattr(candidate, field.name)
        if isinstance(left, np.ndarray):
            assert left.tobytes() == right.tobytes(), field.name
        else:
            assert left == right, field.name
    checked += 1
    return candidate


TemporalMap._view = compare
result = main(sys.argv[1:])
print(f"Full fused array byte parity: {checked} frames; CLI status {result}")
if not checked or result not in (0, 2):
    raise SystemExit(1)
