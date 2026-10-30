"""NOVA plot-serialization regression tests for genuine GCD/OCP handlers."""
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from nox_reader import read_nox
from nova_signal_plots import recover_level_plots


class LevelPlotTests(unittest.TestCase):
    def test_real_level_handler_pairing_and_validation(self):
        def handler(name, x, y):
            return {'__class__':'EcoChemie.Autolab.FunctionHandlers.FHLevel',
                    'FunctionHandler+_name':name, '_params':{'CalcTime':x,'EI_0.CalcPotential':y}}
        charge=handler('FHLevelGalvanostatic',[0.,1.,2.],[.1,.4,.7])
        discharge=handler('FHLevelGalvanostatic',[3.,4.,5.],[.7,.4,.1])
        ocp={'__class__':'EcoChemie.Autolab.FunctionHandlers.FHLevelOcp',
             'FunctionHandler+_name':'FHLevelOcp', '_params':{'CalcTime':[6.,7.], 'EI_0.CalcPotential':[.6,.59]}}
        unknown=handler('FHUnknown',[8.,9.],[.0,.1])
        def plot(par,values=None):
            return {'__class__':'EcoChemie.Shared.SignalSetCommand','CommandBase+_name':'PlotsEvst',
                    'ExecCommandBase+_parent':par,
                    '_params':values or {'X':par['_params']['CalcTime'], 'Y':par['_params']['EI_0.CalcPotential']}}
        objects=[plot(charge),plot(discharge),plot(ocp),plot(unknown),
                 plot(ocp, {'X':[99.,100.], 'Y':[.6,.59]})]  # invalid, duplicate handler
        datasets,warnings=recover_level_plots(objects,None,lambda v,r:v,lambda obj,r:obj['_params'])
        self.assertEqual([ds['kind'] for ds in datasets],['GCD','OCP'])
        self.assertEqual(datasets[0]['point_count'],6)
        self.assertEqual(datasets[0]['cycle_count'],1)
        self.assertEqual(datasets[0]['segment_count'],2)
        self.assertEqual(set(row[2] for row in datasets[0]['values']),{1})
        self.assertEqual(datasets[1]['point_count'],2)
        self.assertEqual(datasets[1]['cycle_count'],1)
        self.assertTrue(warnings)

    def test_bad_plot_axes_are_not_mislabeled(self):
        parent={'__class__':'EcoChemie.Autolab.FunctionHandlers.FHLevel',
                'FunctionHandler+_name':'FHLevelGalvanostatic',
                '_params':{'CalcTime':[0.,1.], 'EI_0.CalcPotential':[.1,.2]}}
        plot={'__class__':'EcoChemie.Shared.SignalSetCommand',
              'CommandBase+_name':'PlotsEvst', 'ExecCommandBase+_parent':parent,
              '_params':{'X':[0.,1.],'Y':[900.,901.]}}
        datasets,warnings=recover_level_plots([plot],None,lambda v,r:v,lambda obj,r:obj['_params'])
        self.assertEqual(datasets,[])
        self.assertTrue(warnings)

    @unittest.skipUnless(os.getenv('METROHM_GCD_SAMPLE'),'Set METROHM_GCD_SAMPLE to an original NOVA GCD file')
    def test_user_gcd_sample(self):
        doc=read_nox(os.environ['METROHM_GCD_SAMPLE'])
        gcd=next(ds for ds in doc['datasets'] if ds['kind']=='GCD')
        self.assertEqual(gcd['point_count'],82795)
        self.assertEqual(gcd['segment_count'],44)
        self.assertGreater(gcd['cycle_count'],15)
        self.assertEqual(gcd['values'][0][0],3.682193990703354)

    @unittest.skipUnless(os.getenv('METROHM_SELF_DISCHARGE_SAMPLE'),'Set METROHM_SELF_DISCHARGE_SAMPLE')
    def test_user_self_discharge_sample(self):
        doc=read_nox(os.environ['METROHM_SELF_DISCHARGE_SAMPLE'])
        self.assertEqual({d['kind'] for d in doc['datasets']},{'CV','GCD','OCP'})
        ocp=next(d for d in doc['datasets'] if d['kind']=='OCP')
        self.assertEqual(ocp['segment_count'],6)
        self.assertEqual(ocp['point_count'],72000)
        self.assertEqual(ocp['cycle_count'],6)

    def test_cycle_ui_present(self):
        cpp=(ROOT/'app/main.cpp').read_text(encoding='utf-8')
        overlay=(ROOT/'app/overlay_workspace.cpp').read_text(encoding='utf-8')
        self.assertIn('setVisibleCycle',cpp)
        self.assertIn('"All cycles"',cpp)
        self.assertIn('curveLookup',cpp)
        self.assertIn('QMap<int,QVector<QPointF>> grouped;',overlay)
        self.assertIn('grouped.size()>1',overlay)

if __name__=='__main__': unittest.main()
