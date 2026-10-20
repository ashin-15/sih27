"""Compare two deterministic temporal demos without printing their large frame records."""

import argparse
import json
from pathlib import Path

import numpy as np


def frames(directory: Path) -> list[dict]:
    with (directory / "frames.jsonl").open(encoding="utf-8") as source:
        return [json.loads(line) for line in source]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()
    reference, candidate = frames(args.reference), frames(args.candidate)
    if len(reference) != len(candidate):
        raise ValueError(f"frame count differs: {len(reference)} != {len(candidate)}")
    fields = ("frame_id", "input_digest", "map_digest", "accounting", "temporal_summary")
    for index, (old, new) in enumerate(zip(reference, candidate, strict=True)):
        for field in fields:
            if old.get(field) != new.get(field):
                raise ValueError(f"frame {index} differs in {field}")
    print(f"Matching frame fields: {len(reference)} frames, {', '.join(fields)}")
    for label, rows in (("reference", reference), ("candidate", candidate)):
        durations = np.array([row["timings_ms"]["temporal_ms"] for row in rows])
        print(
            f"{label}: temporal p50={np.percentile(durations, 50):.3f} ms, "
            f"p95={np.percentile(durations, 95):.3f} ms, "
            f"last5 mean={np.mean(durations[-5:]):.3f} ms"
        )


if __name__ == "__main__":
    main()
