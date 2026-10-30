import csv
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from analysis import analyze_cv, analyze_eis, export_peaks_csv, _savgol
from nox_reader import read_nox

SAMPLE=Path(os.environ.get('METROHM_SAMPLE',ROOT/'examples'/'A110.001.nox'))


def synthetic_cv():
    # Forward anodic and backward cathodic peaks.
    volts=[-0.5+i/100 for i in range(101)] + [0.5-i/100 for i in range(1,101)]
    currents=[(8e-5*math.exp(-((v-0.14)/0.07)**2) if i<=100 else
               -6e-5*math.exp(-((v+0.12)/0.075)**2)) for i,v in enumerate(volts)]
    return {'name':'CV synthetic','kind':'CV','columns':[
        {'key':k,'label':k} for k in ['potential_v','time_s','current_a']],
        'values':[[v,i*0.1,c] for i,(v,c) in enumerate(zip(volts,currents))]}


class AnalysisTests(unittest.TestCase):
    def test_smoothing_constant(self):
        self.assertTrue(all(abs(v-5.)<1e-9 for v in _savgol([5.]*31,9)))

    def test_synthetic_peaks(self):
        d=analyze_cv(synthetic_cv(),window=9,prominence_ua=4)
        self.assertEqual(len(d['peaks']),2)
        pa=next(p for p in d['peaks'] if p['type']=='Oxidation')
        pc=next(p for p in d['peaks'] if p['type']=='Reduction')
        self.assertAlmostEqual(pa['potential_v'],0.14,delta=0.03)
        self.assertAlmostEqual(pc['potential_v'],-0.12,delta=0.03)
        self.assertTrue(pa['width_half_height_v']>0)
        self.assertTrue(pc['width_half_height_v']>0)
        self.assertGreater(next(m['value'] for m in d['metrics'] if m['key']=='q_anodic'),0)
        self.assertLess(next(m['value'] for m in d['metrics'] if m['key']=='q_cathodic'),0)

    def test_prominence_threshold_and_bad_parameters(self):
        self.assertEqual(analyze_cv(synthetic_cv(),prominence_ua=1000)['peaks'],[])
        with self.assertRaises(ValueError):analyze_cv(synthetic_cv(),window=8)
        with self.assertRaises(ValueError):analyze_cv(synthetic_cv(),prominence_ua=-1)

    def test_peak_csv(self):
        output=analyze_cv(synthetic_cv())
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/'peaks.csv'
            export_peaks_csv(output,target)
            with target.open(encoding='utf-8-sig',newline='') as f:
                rows=list(csv.DictReader(f))
            self.assertEqual(len(rows),2)
            self.assertIn('width_half_height_v',rows[0])

    @unittest.skipUnless(SAMPLE.is_file(),'Original .nox sample not found')
    def test_real_nova_data_and_bridge(self):
        doc=read_nox(SAMPLE)
        cv1,cv2,eis=doc['datasets']
        self.assertEqual([202,202,40],[ds['point_count'] for ds in [cv1,cv2,eis]])
        d=analyze_cv(cv1)
        self.assertEqual(len(d['peaks']),2)
        pa=next(p for p in d['peaks'] if p['type']=='Oxidation')
        pc=next(p for p in d['peaks'] if p['type']=='Reduction')
        self.assertAlmostEqual(pa['potential_v'],0.254,delta=0.014)
        self.assertAlmostEqual(pc['potential_v'],0.153,delta=0.014)
        eis_metrics=analyze_eis(eis)['metrics']
        self.assertTrue(any(m['key']=='rct_proxy' for m in eis_metrics))
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/'peaks.csv'
            cmd=[sys.executable,str(ROOT/'backend'/'bridge.py'),'analyze',str(SAMPLE),
                 '--dataset','CV 1','--peaks-csv',str(target)]
            call=subprocess.run(cmd,capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(call.returncode,0,call.stderr)
            self.assertEqual(len(json.loads(call.stdout)['peaks']),2)
            self.assertTrue(target.exists())


if __name__=='__main__':unittest.main()
