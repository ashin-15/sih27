import numpy as np
import pytest

from drishti.config import MappingConfig
from drishti.mapping import resolve_owners


@pytest.mark.parametrize(
    "config",
    [
        MappingConfig(),
        MappingConfig(cell_sizes_cm=(5, 10, 20, 40), radii_m=(10, 25, 50, 100), footprint="square"),
    ],
)
def test_ownership_has_no_overlapping_active_cells_at_seams(config: MappingConfig) -> None:
    rng = np.random.default_rng(26053)
    xy = rng.uniform(-100, 100, (50000, 2))
    sensor = np.array([0.027, -0.038])
    owners = resolve_owners(xy, sensor, config)
    keys = np.unique(np.column_stack([owners.level, owners.indices]), axis=0)
    for fine in range(len(config.ratios) - 1):
        fine_indices = keys[keys[:, 0] == fine, 1:]
        for coarse in range(fine + 1, len(config.ratios)):
            coarse_indices = keys[keys[:, 0] == coarse, 1:]
            ancestor = fine_indices // (config.ratios[coarse] // config.ratios[fine])
            assert not (set(map(tuple, ancestor)) & set(map(tuple, coarse_indices)))
    widths = np.asarray(config.cell_sizes_cm)[owners.level] / 100
    low = owners.indices * widths[:, None]
    assert np.all(xy >= low - 1e-12)
    assert np.all(xy < low + widths[:, None] + 1e-12)


def test_negative_coordinates_and_half_open_lattice_boundaries() -> None:
    x = np.array(
        [
            np.nextafter(-0.05, -np.inf),
            -0.05,
            np.nextafter(-0.05, np.inf),
            np.nextafter(0.05, -np.inf),
            0.05,
            np.nextafter(0.05, np.inf),
        ]
    )
    xy = np.column_stack([x, np.zeros(len(x))])
    owners = resolve_owners(xy, np.zeros(2), MappingConfig())
    assert owners.level.tolist() == [0] * 6
    assert owners.indices[:, 0].tolist() == [-2, -1, -1, 0, 1, 1]


def test_entire_coarse_block_is_promoted_when_it_intersects_finer_radius() -> None:
    points = np.array([[9.97, 0.0], [10.07, 0.0]])
    owners = resolve_owners(points, np.array([0.025, 0]), MappingConfig())
    assert owners.level.tolist() == [0, 0]
