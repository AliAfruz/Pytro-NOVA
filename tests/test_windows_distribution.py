"""Source contracts for reproducible Windows binary distribution.

These tests validate packaging wiring, not executable runtime behavior; the
GitHub Windows runner performs native build/deployment and embedded-Python smoke.
"""
from pathlib import Path
import unittest
import re

ROOT = Path(__file__).resolve().parents[1]


class WindowsDistributionContracts(unittest.TestCase):
    def test_qt_uses_packaged_interpreter(self):
        source = (ROOT / 'app/main.cpp').read_text(encoding='utf-8')
        self.assertIn('NOVA_PYTHON', source)
        self.assertIn('python/python.exe', source)
        self.assertIn('--verify-runtime', source)
        self.assertIn('backend/bridge.py', source)

    def test_packager_bundles_python_qt_backend_and_txt_cli(self):
        script = (ROOT / 'scripts/package_windows.ps1').read_text(encoding='utf-8')
        for marker in ('windeployqt.exe', 'qwindows.dll', 'backend',
                       'nova_to_txt.py', 'python.exe', 'requirements-advanced.txt',
                       'SYNTHETIC_GCD.csv', 'manifest.json', 'Compress-Archive'):
            with self.subTest(marker=marker):
                self.assertIn(marker, script)

    def test_packaged_source_paths_exist(self):
        script = (ROOT / 'scripts/package_windows.ps1').read_text(encoding='utf-8')
        paths = re.findall(r"Copy-Item \(Join-Path \$root '([^']+)'", script)
        self.assertTrue(paths)
        for source_path in paths:
            with self.subTest(source_path=source_path):
                self.assertTrue((ROOT / source_path).exists(), source_path)

    def test_exe_and_portable_zip_have_one_version(self):
        cmake = (ROOT / 'CMakeLists.txt').read_text(encoding='utf-8')
        workflow = (ROOT / '.github/workflows/windows.yml').read_text(encoding='utf-8')
        installer = (ROOT / 'packaging/windows/PytroNOVA.iss').read_text(encoding='utf-8')
        self.assertIn('VERSION 3.9.5', cmake)
        self.assertIn('Pytro-NOVA-v3.9.5-Windows-x64.zip', workflow)
        self.assertIn('Pytro-NOVA-Setup-v3.9.5-Windows-x64.exe', workflow)
        self.assertIn('#define AppVersion "3.9.5"', installer)

    def test_windows_workflow_has_both_artifacts(self):
        workflow = (ROOT / '.github/workflows/windows.yml').read_text(encoding='utf-8')
        self.assertIn('runs-on: windows-2022', workflow)
        self.assertIn('actions/upload-artifact@v4', workflow)
        self.assertIn('Pytro-NOVA-Windows-Portable', workflow)
        self.assertIn('Pytro-NOVA-Windows-Installer', workflow)
        self.assertIn('workflow_dispatch:', workflow)


if __name__ == '__main__':
    unittest.main()
