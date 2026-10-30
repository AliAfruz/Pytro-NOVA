import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE = ROOT / "backend" / "bridge.py"


class BridgeTests(unittest.TestCase):
    def invoke(self, *args):
        return subprocess.run([sys.executable, str(BRIDGE), *map(str, args)],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, encoding="utf-8")

    def test_missing_file_returns_nonzero_and_no_json(self):
        p = self.invoke("read", "/nonexistent/location/file.nox")
        self.assertNotEqual(p.returncode, 0)
        self.assertEqual(p.stdout, "")
        self.assertIn("ERROR", p.stderr)

    @unittest.skipUnless(os.environ.get("METROHM_SAMPLE"), "Set METROHM_SAMPLE to original .nox file")
    def test_round_trip_json_and_csv(self):
        sample = os.environ["METROHM_SAMPLE"]
        p = self.invoke("read", sample)
        self.assertEqual(p.returncode, 0, p.stderr)
        doc = json.loads(p.stdout)
        self.assertEqual([(d["kind"], d["point_count"]) for d in doc["datasets"]],
                         [("CV", 202), ("CV", 202), ("EIS", 40)])
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "CV1.csv"
            p2 = self.invoke("export", sample, "--file", out, "--dataset", "CV 1")
            self.assertEqual(p2.returncode, 0, p2.stderr)
            self.assertEqual(json.loads(p2.stdout)["datasets"], 1)
            self.assertEqual(len(out.read_text(encoding="utf-8-sig").splitlines()), 203)
            p3 = self.invoke("export", sample, "--dir", tmp)
            self.assertEqual(p3.returncode, 0, p3.stderr)
            self.assertEqual(json.loads(p3.stdout)["datasets"], 3)
            self.assertEqual(len(list(Path(tmp).glob("*.csv"))), 4)


if __name__ == "__main__":
    unittest.main()
