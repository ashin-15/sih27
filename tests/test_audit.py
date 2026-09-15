import unittest

from foveamap.data.audit import validate_label_values


class LabelValidationTests(unittest.TestCase):
    def test_accepts_known_lidarseg_indexes(self) -> None:
        result = validate_label_values([0, 1, 16, 31], {0, 1, 16, 31})
        self.assertTrue(result["valid"])
        self.assertEqual(result["invalid_values"], [])

    def test_rejects_unknown_indexes(self) -> None:
        result = validate_label_values([0, 32, 255], {0, 1, 31})
        self.assertFalse(result["valid"])
        self.assertEqual(result["invalid_values"], [32, 255])


if __name__ == "__main__":
    unittest.main()
