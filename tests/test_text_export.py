"""End-to-end and numerical-integrity tests for the clean TXT export."""
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from text_export import export_text_package


def doc():
    return {
        'metadata': {'file': 'laboratory.nox', 'instrument': 'test fixture'},
        'warnings': ['Segment cycle IDs are inferred, not instrument measured'],
        'datasets': [
            {
                'name': 'CV 1', 'kind': 'CV', 'point_count': 2,
                'columns': [
                    {'key': 'potential_v', 'label': 'Applied potential (V)'},
                    {'key': 'current_a', 'label': 'Current (A)'},
                    {'key': 'time_s', 'label': 'Time (s)'},
                ],
                'values': [[0.12345678912345678, 1.2e-8, 0], [-0.2, -9e-7, 0.5]],
            },
            {
                'name': 'GCD 1', 'kind': 'GCD', 'point_count': 4,
                'cycle_source': 'inferred from potential trends',
                'columns': [
                    {'key': 'time_s', 'label': 'Time (s)'},
                    {'key': 'potential_v', 'label': 'Potential (V)'},
                    {'key': 'segment', 'label': 'Recorded segment'},
                    {'key': 'cycle', 'label': 'Inferred cycle'},
                ],
                'values': [[0., 0.3, 1, 1], [1., 0.5, 1, 1],
                           [3., 0.49, 2, 1], [4., 0.35, 2, 1]],
            },
        ],
    }


def tsv(path):
    with path.open(encoding='utf-8', newline='') as f:
        return list(csv.reader(f, delimiter='\t'))


class TextExportTests(unittest.TestCase):
    def test_tables_plot_and_recorded_segments_preserve_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = export_text_package(doc(), 'laboratory.nox', tmp)
            folder = Path(result['folder'])
            self.assertEqual(result['datasets'], 2)
            self.assertEqual(result['data_points'], 6)
            self.assertEqual(result['text_files'], 6)  # two full, two XY, two segments
            cv_raw = tsv(folder / 'full_data/01_CV_1_All_Columns.txt')
            self.assertEqual(cv_raw[0], ['Applied potential (V)', 'Current (A)', 'Time (s)'])
            self.assertEqual(float(cv_raw[1][0]), doc()['datasets'][0]['values'][0][0])
            self.assertEqual(float(cv_raw[1][1]), 1.2e-8)
            cv_plot = tsv(folder / 'plot_data/01_CV_1_Current_vs_Voltage.txt')
            self.assertEqual(cv_plot[0], ['Applied potential (V)', 'Current (A)'])
            self.assertEqual(len(cv_plot), 3)
            original_gcd = tsv(folder / 'full_data/02_GCD_1_All_Columns.txt')
            self.assertEqual(len(original_gcd), 5)
            seg1 = tsv(folder / 'recorded_segments/02_GCD_1_Segment_0001.txt')
            seg2 = tsv(folder / 'recorded_segments/02_GCD_1_Segment_0002.txt')
            self.assertEqual([float(row[0]) for row in seg1[1:]], [0, 1])
            self.assertEqual([float(row[0]) for row in seg2[1:]], [3, 4])
            self.assertEqual(json.loads((folder / 'manifest.json').read_text())['warnings'],
                             doc()['warnings'])
            self.assertEqual(json.loads((folder / 'manifest.json').read_text())['datasets'][1]['cycle_source'],
                             'inferred from potential trends')

    def test_does_not_overwrite_and_selects_exact_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            first = export_text_package(doc(), 'input.nox', tmp, dataset_name='CV 1')
            second = export_text_package(doc(), 'input.nox', tmp, dataset_name='CV 1')
            self.assertNotEqual(first['folder'], second['folder'])
            self.assertEqual(first['text_files'], 2)
            with self.assertRaisesRegex(ValueError, 'not found'):
                export_text_package(doc(), 'input.nox', tmp, dataset_name='unknown')

    def test_invalid_row_does_not_publish_partial_output(self):
        fake = doc()
        fake['datasets'][1]['values'][3][1] = float('nan')
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'Nonfinite'):
                export_text_package(fake, 'bad.nox', tmp)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_importer_to_exporter_cli(self):
        sample = ROOT / 'examples/new_techniques/SYNTHETIC_GCD.csv'
        with tempfile.TemporaryDirectory() as tmp:
            cmd = [sys.executable, str(ROOT / 'tools/nova_to_txt.py'), str(sample),
                   '-o', tmp, '--technique', 'GCD']
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            data = json.loads(proc.stdout)
            self.assertEqual(data['datasets'], 1)
            self.assertEqual(data['text_files'], 2)
            self.assertEqual(len(tsv(Path(data['folder']) / 'full_data/01_GCD_1_All_Columns.txt')),
                             data['data_points'] + 1)

    def test_eis_plot_files(self):
        eis = {'name': 'EIS 1', 'kind': 'EIS', 'point_count': 1,
               'columns': [{'key': key, 'label': label} for key, label in (
                   ('frequency_hz', 'Frequency (Hz)'), ('z_real_ohm', "Z' (ohm)"),
                   ('neg_z_imag_ohm', "-Z'' (ohm)"), ('z_mod_ohm', '|Z| (ohm)'),
                   ('neg_phase_deg', '-Phase (deg)'))],
               'values': [[10, 11, 3, 11.4, 15.]]}
        with tempfile.TemporaryDirectory() as tmp:
            result = export_text_package({'datasets': [eis]}, 'EIS.nox', tmp)
            self.assertEqual(result['text_files'], 4)
            self.assertEqual(len(list((Path(result['folder']) / 'plot_data').glob('*.txt'))), 3)


if __name__ == '__main__':
    unittest.main()
