"""Safely export tensor-only PyTorch weights for the isolated FRNet CPU probe."""

import argparse
import hashlib
from pathlib import Path

import numpy as np
import torch


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    with args.checkpoint.open("rb") as checkpoint_file:
        digest = hashlib.file_digest(checkpoint_file, "sha256").hexdigest()
    if digest != args.sha256:
        raise ValueError("checkpoint SHA-256 mismatch")
    state = torch.load(args.checkpoint, map_location="cpu", weights_only=True)["state_dict"]
    if not all(isinstance(value, torch.Tensor) for value in state.values()):
        raise ValueError("checkpoint contains non-tensor values")
    if not all(
        bool(torch.isfinite(value).all()) for value in state.values() if value.is_floating_point()
    ):
        raise ValueError("checkpoint contains nonfinite floating values")
    np.savez(args.output, **{key: value.numpy() for key, value in state.items()})
    print(f"exported {len(state)} tensors from {digest}")


if __name__ == "__main__":
    main()
