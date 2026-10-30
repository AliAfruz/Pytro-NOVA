"""Numerical regression tests with known synthetic electrochemical signals.

These are software correctness checks, not scientific validation against
instrument standards or certified circuit benchmarks.
"""
import math
import sys
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from advanced import advanced_cv, compare_cv, advanced_eis, eis_impedance, dependencies
from nox_reader import read_nox

np, *_ = dependencies()


def dataset(kind, name, keys, rows):
    return {'kind':kind,'name':name,'columns':[{'key':k,'label':k} for k in keys],
            'values':rows,'point_count':len(rows)}


def make_cv(name='CV 1', offset=0, shift=0):
    x=np.r_[np.linspace(-.6,.6,160),np.linspace(.6,-.6,160)[1:]]
    # Realistic multiple components and a slowly varying capacitive background.
    y=offset+6*x+38*np.exp(-.5*((x-(.19+shift))/.055)**2)
    y-=31*np.exp(-.5*((x-(-.16+shift))/.065)**2)
    t=np.arange(len(x))*.2
    rows=[[float(xx),float(tt),float(yy*1e-6),1.,1, i,0.,0.]
          for i,(xx,tt,yy) in enumerate(zip(x,t,y))]
    return dataset('CV',name,['potential_v','time_s','current_a','we_potential_v','scan','index','q_plus_c','q_minus_c'],rows)


def make_eis(circuit,params):
    f=np.logspace(5,-2,70)
    z=eis_impedance(f,params,circuit,np)
    rows=[[float(ff),float(zz.real),float(-zz.imag),float(abs(zz)),float(-np.angle(zz,deg=True))]
          for ff,zz in zip(f,z)]
    return dataset('EIS','EIS 1',['frequency_hz','z_real_ohm','neg_z_imag_ohm','z_mod_ohm','neg_phase_deg'],rows)


class AdvancedTests(unittest.TestCase):
    def test_cv_gaussian_baseline(self):
        d=make_cv()
        r=advanced_cv(d,baseline='asls',shape='gaussian',components=2)
        self.assertGreaterEqual(len(r['rows']),2)
        self.assertTrue(any(abs(x['center_v']-.19)<.07 for x in r['rows'] if x['type']=='Oxidation'))
        self.assertTrue(any(abs(x['center_v']+.16)<.07 for x in r['rows'] if x['type']=='Reduction'))
        self.assertTrue(all(x['fwhm_mv']>0 for x in r['rows']))
        self.assertTrue(r['plot']['series'])

    def test_cv_lorentzian(self):
        r=advanced_cv(make_cv(),baseline='linear',shape='lorentzian',components=2)
        self.assertTrue(all(x['shape']=='lorentzian' for x in r['rows']))

    def test_cv_invalid_parameters(self):
        with self.assertRaises(ValueError):advanced_cv(make_cv(),components=0)

    def test_multi_cv_comparison(self):
        r=compare_cv([make_cv('CV 1'),make_cv('CV 2',offset=3.)])
        self.assertEqual(len(r['rows']),2)
        self.assertAlmostEqual(r['rows'][0]['branch_rmse_ua'],0,places=7)
        self.assertAlmostEqual(r['rows'][1]['branch_rmse_ua'],3.,delta=.3)

    def test_rc_fit(self):
        result=advanced_eis(make_eis('randles_rc',[12,55,1.5e-4]),circuit='randles_rc')
        params={x['parameter']:x['value'] for x in result['rows']}
        self.assertAlmostEqual(params['Rs'],12,delta=.05)
        self.assertAlmostEqual(params['Rct'],55,delta=.15)
        self.assertAlmostEqual(params['Cdl'],1.5e-4,delta=2e-6)
        self.assertLess(result['summary'][0]['value'],.1)

    def test_cpe_fit(self):
        result=advanced_eis(make_eis('randles_cpe',[12,55,2e-4,.87]),circuit='randles_cpe')
        params={x['parameter']:x['value'] for x in result['rows']}
        self.assertAlmostEqual(params['Rs'],12,delta=.05)
        self.assertAlmostEqual(params['Rct'],55,delta=.15)
        self.assertAlmostEqual(params['α'],.87,delta=.005)
        self.assertLess(result['summary'][0]['value'],.1)

    def test_warburg_fit(self):
        result=advanced_eis(make_eis('randles_cpe_warburg',[12,55,2e-4,.88,5]),circuit='randles_cpe_warburg')
        self.assertLess(result['summary'][0]['value'],1.0)
        self.assertEqual(len(result['rows']),5)

    def test_real_sample(self):
        f=Path(os.environ.get('METROHM_SAMPLE', ROOT/'examples'/'A110.001.nox'))
        if not f.exists():self.skipTest('Uploaded .nox sample not available')
        datasets=read_nox(f)['datasets']
        self.assertEqual([d['point_count'] for d in datasets],[202,202,40])
        for d in datasets:
            r=advanced_cv(d) if d['kind']=='CV' else advanced_eis(d)
            self.assertGreater(len(r['plot']['series']),0)
        self.assertEqual(len(compare_cv(datasets)['rows']),2)


if __name__=='__main__':unittest.main()
