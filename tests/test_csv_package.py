"""Minimal plot CSV regression tests (no duplicate raw/analysis CSV files)."""
import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from csv_package import export_csv_package
from nox_reader import read_nox


def rows(file):
    with open(file, newline='', encoding='utf-8-sig') as stream:
        return list(csv.reader(stream))


def example_doc():
    cv = {'name': 'CV 1', 'kind': 'CV',
          'columns': [
              {'key': 'potential_v', 'label': 'Applied potential (V)'},
              {'key': 'time_s', 'label': 'Time (s)'},
              {'key': 'current_a', 'label': 'WE(1) current (A)'},
          ], 'point_count': 2,
          'values': [[0.12345678912345678, 0, -2.3456789012345e-7],
                     [-0.5, 1, 9.876543210123456e-6]]}
    eis = {'name': 'EIS 1', 'kind': 'EIS',
           'columns': [
               {'key': 'frequency_hz', 'label': 'Frequency (Hz)'},
               {'key': 'z_real_ohm', 'label': "Z' (ohm)"},
               {'key': 'neg_z_imag_ohm', 'label': "-Z'' (ohm)"},
               {'key': 'z_mod_ohm', 'label': '|Z| (ohm)'},
               {'key': 'neg_phase_deg', 'label': '-Phase (deg)'},
           ], 'point_count': 2,
           'values': [[1000., 7.123456789123456, 3.2, 7.808, 11.1],
                      [0.1, 45., 28.5, 53.2, 32.5]]}
    return {'metadata': {}, 'datasets': [cv, eis]}


class PlotCSVTests(unittest.TestCase):
    def test_cv_and_eis_export_exactly_four_two_column_files(self):
        doc = example_doc()
        with tempfile.TemporaryDirectory() as root:
            summary = export_csv_package(doc, 'measure.nox', root)
            folder = Path(summary['folder'])
            csv_files = sorted(folder.rglob('*.csv'))
            self.assertEqual(summary['csv_files'], 4)
            self.assertEqual(len(csv_files), 4)
            self.assertEqual([f.name for f in csv_files], sorted([
                '01_CV_1_Current_vs_Voltage.csv', '02_EIS_1_Nyquist.csv',
                '02_EIS_1_Bode_Magnitude.csv', '02_EIS_1_Bode_Phase.csv',
            ]))
            self.assertEqual(summary['data_points'], 4)
            cv_rows = rows(folder / '01_CV_1_Current_vs_Voltage.csv')
            self.assertEqual(cv_rows[0], ['Applied potential (V)', 'WE(1) current (A)'])
            self.assertEqual([list(map(float, row)) for row in cv_rows[1:]],
                             [[p[0], p[2]] for p in doc['datasets'][0]['values']])
            e = doc['datasets'][1]['values']
            for name, expected, header in [
                ('Nyquist', [[r[1], r[2]] for r in e], ["Z' (ohm)", "-Z'' (ohm)"]),
                ('Bode_Magnitude', [[r[0], r[3]] for r in e], ['Frequency (Hz)', '|Z| (ohm)']),
                ('Bode_Phase', [[r[0], r[4]] for r in e], ['Frequency (Hz)', '-Phase (deg)']),
            ]:
                data = rows(folder / f'02_EIS_1_{name}.csv')
                self.assertEqual(data[0], header)
                self.assertEqual([list(map(float, r)) for r in data[1:]], expected)
            # No 32-file bundles, duplicate measurement files, peaks or metadata CSVs.
            self.assertEqual(list(folder.glob('raw_data')), [])
            self.assertEqual(list(folder.glob('analysis')), [])
            self.assertTrue((folder / 'README.txt').exists())

    def test_selected_dataset_and_non_overwriting_folder(self):
        doc = example_doc()
        with tempfile.TemporaryDirectory() as root:
            cv = export_csv_package(doc, 'measure.nox', root, 'CV 1')
            eis = export_csv_package(doc, 'measure.nox', root, 'EIS 1')
            self.assertEqual(cv['csv_files'], 1)
            self.assertEqual(eis['csv_files'], 3)
            self.assertNotEqual(cv['folder'], eis['folder'])
            with self.assertRaisesRegex(ValueError, 'not found'):
                export_csv_package(doc, 'measure.nox', root, 'CV 99')

    @unittest.skipUnless(os.environ.get('METROHM_SAMPLE'), 'Need METROHM_SAMPLE')
    def test_sample_and_cli(self):
        source = os.environ['METROHM_SAMPLE']
        doc = read_nox(source)
        with tempfile.TemporaryDirectory() as root:
            result = export_csv_package(doc, source, root)
            self.assertEqual(result['csv_files'], 5)
            self.assertEqual(result['datasets'], 3)
            folder = Path(result['folder'])
            self.assertEqual(len(rows(folder / '01_CV_1_Current_vs_Voltage.csv')) - 1, 202)
            self.assertEqual(len(rows(folder / '03_EIS_1_Nyquist.csv')) - 1, 40)
            for idx, ds in enumerate(doc['datasets'], 1):
                kind = ds['kind']
                key = 'Current_vs_Voltage' if kind == 'CV' else 'Bode_Phase'
                row_data = rows(folder / f'{idx:02d}_{ds["name"].replace(" ", "_")}_{key}.csv')
                self.assertEqual(len(row_data) - 1, ds['point_count'])
            call = subprocess.run([sys.executable, str(ROOT / 'backend' / 'bridge.py'),
                                   'export-package', source, '--dir', root, '--dataset', 'EIS 1'],
                                  capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(call.returncode, 0, call.stderr)
            self.assertEqual(json.loads(call.stdout)['csv_files'], 3)

    def test_no_excel_action(self):
        call = subprocess.run([sys.executable, str(ROOT / 'backend' / 'bridge.py'), '--help'],
                              capture_output=True, text=True, encoding='utf-8')
        self.assertNotIn('export-xlsx', call.stdout)


if __name__ == '__main__':
    unittest.main()
