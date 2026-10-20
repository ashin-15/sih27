"""Time exact receipt cell-overlap checks on one real current-path payload."""

import argparse
from time import perf_counter
from typing import Any

import numpy as np

from drishti import product_result
from drishti.cli import main
from drishti.visibility import pack_cells


def previous(level: Any, indices: Any, sizes: tuple[int, ...]) -> bool:
    packed = pack_cells(level, indices)
    if len(np.unique(packed)) != len(packed):
        return True
    for finer_level in range(len(sizes)):
        finer = indices[level == finer_level]
        for coarser in range(finer_level + 1, len(sizes)):
            ratio = sizes[coarser] // sizes[finer_level]
            parents = pack_cells(np.full(len(finer), coarser, dtype=np.int64), finer // ratio)
            if np.any(np.isin(parents, packed)):
                return True
    return False


def current(level: Any, indices: Any, sizes: tuple[int, ...]) -> bool:
    packed = np.sort(pack_cells(level, indices))
    if np.any(packed[1:] == packed[:-1]):
        return True
    for finer_level in range(len(sizes)):
        finer = indices[level == finer_level]
        for coarser in range(finer_level + 1, len(sizes)):
            ratio = sizes[coarser] // sizes[finer_level]
            parents = pack_cells(np.full(len(finer), coarser, dtype=np.int64), finer // ratio)
            if len(parents):
                positions = np.searchsorted(packed, parents)
                valid = positions < len(packed)
                if np.any(packed[positions[valid]] == parents[valid]):
                    return True
    return False


def screen() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--repeats", type=int, default=10)
    args = parser.parse_args()
    if args.repeats <= 0:
        raise ValueError("repeats must be positive")
    captured: list[Any] = []
    original = product_result._validate_cells

    def capture(frame: Any, result: Any, deep: bool = True) -> None:
        if result.frame_id == 1:
            captured.append(result.cells)
        original(frame, result, deep)

    product_result._validate_cells = capture
    try:
        exit_code = main(
            [
                "replay",
                "--dataset",
                "../data/semantickitti",
                "--sequence",
                "08",
                "--mode",
                "learned",
                "--device",
                "cuda",
                "--frnet-runtime",
                "torch",
                "--frnet-checkpoint",
                "../data/frnet-semantickitti_seg.pth",
                "--frnet-checkpoint-sha256",
                "09adea9005215641aea915cc3aa2bebf74582ce240cca91dedd07940ad94285e",
                "--detect-obstacles",
                "--track-obstacles",
                "--visibility",
                "--temporal",
                "--evaluate-product-contract",
                "--audit-every",
                "100",
                "--view",
                "none",
                "--max-frames",
                "2",
                "--output",
                args.output,
            ]
        )
    finally:
        product_result._validate_cells = original
    if exit_code != 0 or len(captured) != 1:
        raise RuntimeError("two-frame replay did not provide one accepted warm payload")
    cells = captured[0]
    arguments = (cells.level, cells.indices, cells.cell_sizes_cm)
    if previous(*arguments) or current(*arguments):
        raise ValueError("accepted payload unexpectedly contains overlapping cells")
    for name, method in (("previous", previous), ("current", current)):
        start = perf_counter()
        for _ in range(args.repeats):
            method(*arguments)
        elapsed_ms = (perf_counter() - start) * 1000 / args.repeats
        print(f"{name}={elapsed_ms:.3f} ms cells={len(cells.level)}", flush=True)


if __name__ == "__main__":
    screen()
