"""Static C++ integration contract and reader-data validation.

C++ itself must be compiled with Qt 6 on Windows (not available in this test host).
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from nox_reader import read_nox

class OverlayContractTests(unittest.TestCase):
    def test_native_plot_context_menu_integrated(self):
        source = (ROOT / "app" / "main.cpp").read_text(encoding="utf-8")
        for expected in ["customContextMenuRequested", "Send CV current vs voltage to Overlay",
                         "Send EIS Nyquist to Overlay", "Send EIS Bode magnitude to Overlay",
                         "Send EIS Bode phase to Overlay", "openOverlay();", "sendToOverlay("]:
            self.assertIn(expected, source)

    def test_strict_family_and_axis_groups(self):
        source = (ROOT / "app" / "overlay_workspace.cpp").read_text(encoding="utf-8")
        self.assertIn('if(kind!=modeKind(mode))', source)
        self.assertIn('if(key==xKey(mode))', source)
        self.assertIn('if(key==yKey(mode))', source)
        self.assertIn('if(x<0||y<0)', source)
        self.assertIn('return {std::log10(raw.x()), raw.y()};', source)
        self.assertIn('return {raw.x(), raw.y()*1e6};', source)
        self.assertIn('QString::number(pt.x(),\'g\',17)', source)

    def test_split_source_project(self):
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        self.assertIn('app/overlay_workspace.cpp', cmake)
        self.assertIn('app/advanced_dialog.cpp', cmake)
        self.assertIn('PRIVATE $<$<CONFIG:Release>:-O0> -g0', cmake)

    def test_qt6_overlay_headers_and_color_palette_lookup(self):
        source = (ROOT / "app" / "overlay_workspace.cpp").read_text(encoding="utf-8")
        # Qt 6 only forward-declares QJsonArray in some headers; it must be included
        # when constructing QJsonArray values. QWidget also has palette().
        self.assertIn("#include <QtCore/QJsonArray>", source)
        self.assertIn("const std::array<QColor, 10> curvePalette{", source)
        self.assertIn("curve.color=curvePalette.at(", source)
        self.assertNotIn("curve.color=palette.at(", source)

    def test_actual_sample_all_overlay_axes_present(self):
        sample = Path(__import__('os').environ.get('METROHM_SAMPLE', ''))
        if not sample.is_file(): self.skipTest('Set METROHM_SAMPLE to a .nox file')
        doc = read_nox(sample)
        expected = {
            'CV': [('potential_v','current_a')],
            'EIS': [('z_real_ohm','neg_z_imag_ohm'),
                    ('frequency_hz','z_mod_ohm'),
                    ('frequency_hz','neg_phase_deg')]
        }
        for ds in doc['datasets']:
            keys = {col['key'] for col in ds['columns']}
            for x, y in expected[ds['kind']]:
                self.assertIn(x, keys)
                self.assertIn(y, keys)
            if ds['kind']=='EIS':
                fi = [c['key'] for c in ds['columns']].index('frequency_hz')
                self.assertTrue(all(row[fi] > 0 for row in ds['values']))

if __name__=='__main__': unittest.main()
