import tempfile
import unittest
from pathlib import Path

from foveamap.data.discovery import discover_dataset_root, validate_dataset_root


REQUIRED_PATHS = (
    "v1.0-mini/sample.json",
    "v1.0-mini/sample_data.json",
    "v1.0-mini/category.json",
    "v1.0-mini/lidarseg.json",
    "samples/LIDAR_TOP",
    "sweeps/LIDAR_TOP",
    "lidarseg/v1.0-mini",
)


def make_dataset(root: Path) -> None:
    for relative in REQUIRED_PATHS:
        path = root / relative
        if path.suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("[]", encoding="utf-8")
        else:
            path.mkdir(parents=True, exist_ok=True)


class DatasetDiscoveryTests(unittest.TestCase):
    def test_selects_single_valid_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "vyomkeshsharma" / "nuscenes-mini-complete-with-lidarseg"
            make_dataset(root)
            selected = discover_dataset_root(temp_dir)
            self.assertEqual(selected.path, root)
            self.assertEqual(selected.missing_paths, ())

    def test_rejects_ambiguous_roots(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            make_dataset(Path(temp_dir) / "first" / "nuscenes-mini")
            make_dataset(Path(temp_dir) / "second" / "nuscenes-mini")
            with self.assertRaisesRegex(RuntimeError, "Ambiguous dataset roots"):
                discover_dataset_root(temp_dir, preferred_slug="absent/dataset")

    def test_reports_missing_contract_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "dataset"
            (root / "v1.0-mini").mkdir(parents=True)
            (root / "v1.0-mini" / "sample.json").write_text("[]", encoding="utf-8")
            result = validate_dataset_root(root)
            missing_names = {path.name for path in result.missing_paths}
            self.assertIn("sample_data.json", missing_names)
            self.assertIn("LIDAR_TOP", missing_names)


if __name__ == "__main__":
    unittest.main()
