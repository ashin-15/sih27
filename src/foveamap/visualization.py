from __future__ import annotations

from pathlib import Path
from typing import Any


def _pyplot():
    import matplotlib

    matplotlib.use("Agg", force=True)
    import matplotlib.pyplot as plt

    return plt


def _add_range_rings(axis: Any, radii: tuple[float, ...] = (10.0, 25.0, 50.0, 75.0, 100.0)) -> None:
    import numpy as np

    theta = np.linspace(0.0, 2.0 * np.pi, 256)
    for radius in radii:
        axis.plot(radius * np.cos(theta), radius * np.sin(theta), linestyle="--", linewidth=0.5, color="white", alpha=0.55)
        axis.text(radius, 0.0, f"{radius:g}m", color="white", fontsize=8)


def render_height_bev(points: Any, output_path: str | Path, title: str = "LiDAR BEV — height") -> Path:
    plt = _pyplot()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(8, 8))
    scatter = axis.scatter(points[:, 0], points[:, 1], c=points[:, 2], s=0.4, cmap="viridis", marker=".")
    axis.set_title(title)
    axis.set_xlabel("x (m, forward)")
    axis.set_ylabel("y (m, left)")
    axis.set_aspect("equal")
    axis.grid(True, alpha=0.2)
    _add_range_rings(axis)
    figure.colorbar(scatter, ax=axis, label="height (m)", fraction=0.046, pad=0.04)
    figure.tight_layout()
    figure.savefig(output_path, dpi=180)
    plt.close(figure)
    return output_path


def render_semantic_bev(
    points: Any,
    labels: Any,
    category_names: dict[int, str],
    output_path: str | Path,
    title: str = "LiDAR BEV — lidarseg class",
) -> Path:
    plt = _pyplot()
    from matplotlib import colors

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    max_index = max(max(category_names, default=0), int(labels.max()) if len(labels) else 0)
    cmap = plt.colormaps["tab20"].resampled(max_index + 1)
    norm = colors.BoundaryNorm(boundaries=[-0.5 + value for value in range(max_index + 2)], ncolors=max_index + 1)

    figure, axis = plt.subplots(figsize=(9, 8))
    scatter = axis.scatter(points[:, 0], points[:, 1], c=labels, s=0.4, cmap=cmap, norm=norm, marker=".")
    axis.set_title(title)
    axis.set_xlabel("x (m, forward)")
    axis.set_ylabel("y (m, left)")
    axis.set_aspect("equal")
    axis.grid(True, alpha=0.2)
    _add_range_rings(axis)
    colorbar = figure.colorbar(scatter, ax=axis, fraction=0.046, pad=0.04)
    colorbar.set_ticks(range(max_index + 1))
    colorbar.set_ticklabels([category_names.get(index, str(index)) for index in range(max_index + 1)])
    figure.tight_layout()
    figure.savefig(output_path, dpi=180)
    plt.close(figure)
    return output_path
