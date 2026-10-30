import sys
import os
import unittest
from pathlib import Path
import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from auto_eis import extract_spectrum, smooth_eis, analyze_auto_eis, FAST_MODELS, DEEP_MODELS, EXHAUSTIVE_MODELS
from afr_eis.models import CIRCUITS


def synthetic(n=32):
    frequency=np.geomspace(1e5,.5,n)
    z=CIRCUITS['R-(R||C)'].function(frequency,12.0,170.0,2e-5)
    return {'kind':'EIS','name':'EIS synthetic',
            'columns':[{'key': k} for k in ('frequency_hz','z_real_ohm','neg_z_imag_ohm')],
            'values':[[float(f),float(v.real),float(-v.imag)] for f,v in zip(frequency,z)]}

class AutoEISTests(unittest.TestCase):
    def test_smoothing_off_exact(self):
        f,z=extract_spectrum(synthetic())
        smooth,w,_=smooth_eis(f,z,'off')
        self.assertEqual(w,0)
        np.testing.assert_array_equal(z,smooth)

    def test_auto_and_strong_smooth_finite(self):
        f,z=extract_spectrum(synthetic())
        for mode in ['auto','light','strong']:
            smooth,w,_=smooth_eis(f,z,mode)
            self.assertEqual(len(smooth),len(z))
            self.assertTrue(np.all(np.isfinite(smooth)))
            self.assertTrue(w==0 or (w>=5 and w%2==1))

    def test_duplicates_rejected(self):
        ds=synthetic()
        ds['values'][1][0]=ds['values'][0][0]
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            extract_spectrum(ds)

    def test_circuit_count(self):
        self.assertEqual(len(FAST_MODELS),7)
        self.assertEqual(len(DEEP_MODELS),15)
        self.assertEqual(len(EXHAUSTIVE_MODELS),19)

    def test_raw_fit_unmodified(self):
        result=analyze_auto_eis(synthetic(),smoothing='strong',fit_smoothed=False)
        self.assertEqual(result['type'],'eis_auto')
        self.assertGreater(len(result['rows']),2)
        self.assertTrue(result['parameters'])
        self.assertFalse(result['smoothing']['fit_smoothed'])
        self.assertEqual(len(result['diagnostics']['frequency_hz']),32)
        self.assertEqual(len(result['plot']['series']),3)
        self.assertLess(float(next(m['value'] for m in result['summary'] if m['name']=='RMSE vs RAW')),10)

    def test_nox_sample(self):
        path=Path(os.environ.get('METROHM_SAMPLE', Path(__file__).resolve().parents[1]/'examples'/'A110.001.nox'))
        if not path.exists(): self.skipTest('sample .nox not available')
        from nox_reader import read_nox
        ds=next(ds for ds in read_nox(path)['datasets'] if ds['kind']=='EIS')
        result=analyze_auto_eis(ds,search_depth='fast')
        self.assertEqual(result['search']['fitted_count'],7)
        self.assertGreaterEqual(len(result['rows']),6)
        self.assertEqual(len(result['diagnostics']['frequency_hz']),40)

if __name__=='__main__': unittest.main()

# Added regression checks for v3.1 integration defaults.
class AfruzIntegrationRegressionTests(unittest.TestCase):
    def test_proportional_weighting_and_quick_precision(self):
        result = analyze_auto_eis(synthetic(), search_depth='fast',
                                  smoothing='off', weighting='proportional', precision='quick')
        self.assertEqual(result['search']['weighting'], 'proportional')
        self.assertEqual(result['optimizer']['max_nfev'], 900)
        self.assertEqual(result['optimizer']['multistart'], 2)
        self.assertIn(result['fit_quality']['label'], ('poor', 'review', 'numerically close'))
        self.assertLess(result['fit_quality']['relative_rms_raw_percent'], 5)

    def test_ui_starts_in_real_auto_mode_when_eis_available(self):
        source=(Path(__file__).resolve().parents[1] / 'app' / 'advanced_dialog.h').read_text(encoding='utf-8')
        self.assertIn('const int startupMode=autoData_->count()>0 ? 3 : 0;', source)
        self.assertIn('args<<"eis"<<file_<<"--dataset"<<autoData_->currentText()', source)
        self.assertIn('<<"--circuit"<<"auto"', source)
        self.assertIn('<<"--precision"<<precision_->currentData().toString()', source)
