"""Multi-technique decoding, CLI dispatch, analysis, CSV and overlay contracts."""
import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from techniques import TECHNIQUES, make_dataset, read_technique_csv, extract_nox_techniques
from analysis import analyze_dataset
from csv_package import export_csv_package
from bridge import run


class TechniquesTests(unittest.TestCase):
    def synth(self, kind):
        rows={
            'GCD': {'time_s':[0,1,2,3,4], 'potential_v':[0.1,0.3,0.5,0.3,0.1], 'current_a':[.001,.001,.001,-.001,-.001]},
            'LSV': {'potential_v':[-1,-.5,0,.5,1], 'current_a':[0,1e-6,9e-6,1e-6,0]},
            'DPV': {'potential_v':[-1,-.5,0,.5,1], 'current_a':[0,1e-6,9e-6,1e-6,0]},
            'SWV': {'potential_v':[-1,-.5,0,.5,1], 'current_a':[0,1e-6,9e-6,1e-6,0]},
            'CA': {'time_s':[0,1,2,3,4], 'current_a':[.001,.001,.001,.001,.001]},
            'CP': {'time_s':[0,1,2,3,4], 'potential_v':[.1,.2,.3,.4,.5]},
            'OCP': {'time_s':[0,1,2,3,4], 'potential_v':[.1,.2,.3,.4,.5]},
        }
        return make_dataset(kind,1,rows[kind])

    def test_all_techniques_return_numeric_analysis(self):
        for kind in TECHNIQUES:
            with self.subTest(kind=kind):
                ds=self.synth(kind)
                result=analyze_dataset(ds)
                self.assertEqual(result['kind'],kind)
                self.assertIsInstance(result['metrics'],list)
                self.assertEqual(len(ds['values']),ds['point_count'])

    def test_all_techniques_export_exactly_one_plot(self):
        with tempfile.TemporaryDirectory() as folder:
            for kind in TECHNIQUES:
                ds=self.synth(kind)
                out=export_csv_package({'datasets':[ds]},f'{kind}.nox',folder)
                self.assertEqual(out['csv_files'],1)
                path=Path(out['folder'])/out['files'][0]
                with path.open(encoding='utf-8-sig',newline='') as f:
                    rows=list(csv.reader(f))
                self.assertEqual(len(rows),ds['point_count']+1)
                self.assertEqual(len(rows[0]),2)

    def test_csv_explicit_units_and_cli(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'dpv.csv'
            path.write_text('Potential (V),Current (µA)\n0.0,0\n0.1,2.5\n0.2,0\n',encoding='utf-8')
            doc=read_technique_csv(path,'DPV')
            self.assertAlmostEqual(doc['datasets'][0]['values'][1][1],2.5e-6)
            self.assertEqual(run(['read',str(path),'--technique','DPV'])['datasets'][0]['kind'],'DPV')
            out=run(['export-package',str(path),'--dir',folder,'--technique','DPV'])
            self.assertEqual(out['csv_files'],1)
            ana=run(['analyze',str(path),'--dataset','DPV 1','--technique','DPV'])
            self.assertEqual(ana['kind'],'DPV')

    def test_unknown_units_not_silently_assumed(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'data.csv'
            path.write_text('Potential,Current\n0.1,1.0\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'missing'):
                read_technique_csv(path,'LSV')

    def test_bad_csv_length_and_nan(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'data.csv'
            path.write_text('Time (s),Potential (V)\n0,0.1\n1,nan\n',encoding='utf-8')
            with self.assertRaises(ValueError):read_technique_csv(path,'GCD')
        with self.assertRaises(ValueError):
            make_dataset('GCD',1,{'time_s':[0,1],'potential_v':[0.1]})

    def test_no_spurious_nox_technique(self):
        objects=[{'__class__':'EcoChemie.Autolab.FunctionHandlers.FHLinearSweepVoltammetry'}]
        datasets,warnings=extract_nox_techniques(objects,None,None,lambda x,r:{})
        self.assertEqual(datasets,[])
        self.assertTrue(warnings)
        objects=[{'__class__':'EcoChemie.Autolab.FunctionHandlers.FHLinearSweepVoltammetry'}]
        params={'SetpointApplied':[.1,.2,.3], 'EI_0.CalcCurrent':[.1,.2,.3]}
        datasets,warnings=extract_nox_techniques(objects,None,None,lambda x,r:params)
        self.assertEqual([d['kind'] for d in datasets],['LSV'])
        self.assertEqual(datasets[0]['point_count'],3)

    def test_overlay_modes_are_not_mixed(self):
        cpp=(ROOT/'app/overlay_workspace.cpp').read_text()
        header=(ROOT/'app/overlay_workspace.h').read_text()
        for kind in TECHNIQUES:
            self.assertIn('OverlayMode::'+kind,cpp)
            self.assertIn(kind+' =',header)
        self.assertIn('if(kind!=modeKind(mode))',cpp)
        self.assertIn('std::array<QVector<Curve>, 11>',cpp)

if __name__=='__main__': unittest.main()
