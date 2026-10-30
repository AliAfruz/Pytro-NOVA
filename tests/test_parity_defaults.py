from __future__ import annotations
import sys
import json
import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))


class OriginalAfruzParity(unittest.TestCase):
    def test_qt_defaults_mirror_original_gui(self):
        text = (ROOT/'app'/'advanced_dialog.h').read_text(encoding='utf-8')
        self.assertIn('depth_->setCurrentIndex(2);', text)
        self.assertIn('precision_->setCurrentIndex(2);', text)
        self.assertIn('smoothing_->setCurrentIndex(1);', text)
        self.assertNotIn('depth_->setCurrentIndex(1)', text)

    def test_top_rank_not_replaced_by_other_model(self):
        text = (ROOT/'backend'/'auto_eis.py').read_text(encoding='utf-8')
        self.assertIn('best = fits[0]', text)

    def test_original_models_copied_exactly(self):
        provenance=json.loads((ROOT/'docs/licenses/eis-provenance.json').read_text())
        for filename,expected in provenance['files'].items():
            self.assertEqual(hashlib.sha256((ROOT/'backend'/'afr_eis'/filename).read_bytes()).hexdigest(),expected)

if __name__=='__main__':
    unittest.main()
