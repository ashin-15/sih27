from pathlib import Path

import pytest

from drishti.config import MappingConfig, load_config, load_run_config


def test_configuration_rejects_non_nested_resolutions() -> None:
    with pytest.raises(ValueError, match="integer"):
        MappingConfig(cell_sizes_cm=(5, 10, 20, 50), radii_m=(10.0, 25.0, 50.0, 100.0))


def test_configuration_rejects_unknown_options(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text("max_point = 150000\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unknown configuration"):
        load_config(path)


def test_five_to_one_boundary_is_legal() -> None:
    config = MappingConfig(cell_sizes_cm=(5, 10, 50), radii_m=(10.0, 25.0, 100.0))
    assert config.ratios == (1, 2, 10)


def test_run_preset_resolves_paths_relative_to_its_file(tmp_path: Path) -> None:
    preset = tmp_path / "run.toml"
    preset.write_text(
        'dataset_root = "data/dataset"\nartifact_root = "runs"\n'
        'mapping_config = "map.toml"\ncomparison_config = "square.toml"\n'
    )
    config = load_run_config(preset)
    assert config.dataset_root == tmp_path / "data/dataset"
    assert config.mapping_config == tmp_path / "map.toml"
    assert config.artifact_root == tmp_path / "runs"
    assert config.pose_source.value == "slam"
    preset.write_text('dataset_root = "data"\nartifact_root = "runs"\ntypo = 1\n')
    with pytest.raises(ValueError, match="unknown"):
        load_run_config(preset)
