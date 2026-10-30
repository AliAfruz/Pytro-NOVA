"""Source-level Qt 6 size/algorithm regression checks.

This is not a substitute for compiling with a Qt 6.12 toolchain.
"""
from pathlib import Path
import unittest


class QtCompatibilityTests(unittest.TestCase):
    def test_advanced_legend_size_cast(self):
        header = (Path(__file__).resolve().parents[1] / "app" / "advanced_dialog.h").read_text(encoding="utf-8")
        self.assertIn('static_cast<int>(line.name.size())', header)
        self.assertNotIn('std::max(123,20+line.name.size()*6)', header)


if __name__ == "__main__":
    unittest.main()
