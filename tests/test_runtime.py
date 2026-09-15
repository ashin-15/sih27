import json
import tempfile
import unittest
from pathlib import Path

from foveamap.runtime import collect_runtime_report, write_json


class RuntimeReportTests(unittest.TestCase):
    def test_runtime_report_is_json_serializable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report = collect_runtime_report(temp_dir, seed=123)
            encoded = json.dumps(report)
            self.assertIn('"seed": 123', encoded)
            self.assertIn("accelerator", report)

    def test_write_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = write_json({"ok": True}, Path(temp_dir) / "nested" / "report.json")
            self.assertTrue(output.exists())
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), {"ok": True})


if __name__ == "__main__":
    unittest.main()
