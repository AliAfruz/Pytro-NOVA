"""Regressions for overly compressed GCD and false segment joins."""
import os
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from gcd_groups import comparable_cycle_groups
from nox_reader import read_nox


class GcdDisplayFixTests(unittest.TestCase):
    def test_grouping_avoids_mixing_long_and_short_cycles(self):
        # Five synthetic voltage traces: two 5-s, two 120-s, one 3600-s.
        rows=[]
        for group,duration in enumerate([5, 5.2, 120, 118, 3600],1):
            for time,pot in ((0,0.2),(duration/2,0.8),(duration,0.3)):
                rows.append([time,pot,group,group,1,time])
        found,suggested=comparable_cycle_groups([],rows)
        self.assertEqual([g['cycles'] for g in found],[[1,2],[3,4]])
        self.assertEqual(suggested,[1,2])

    def test_source_has_segment_breaks_and_selection_rescaling(self):
        cpp=(ROOT/'app/main.cpp').read_text(encoding='utf-8')
        overlay=(ROOT/'app/overlay_workspace.cpp').read_text(encoding='utf-8')
        self.assertIn('curve.segments.append(QVector<QPointF>{})',cpp)
        self.assertNotIn('curve.segments.append({})',cpp)
        self.assertIn('recomputeVisibleBounds();',cpp)
        self.assertIn('comparable_cycle_groups',cpp)
        self.assertIn('setVisibleCycles',cpp)
        self.assertIn('curve.segmentStarts=',overlay)
        self.assertIn('path.moveTo(pt)',overlay)

    @unittest.skipUnless(os.getenv('METROHM_GCD_SAMPLE'),'Set METROHM_GCD_SAMPLE')
    def test_original_gcd_is_not_modified(self):
        ds=next(d for d in read_nox(os.getenv('METROHM_GCD_SAMPLE'))['datasets'] if d['kind']=='GCD')
        self.assertEqual(ds['point_count'],82795)
        self.assertEqual(ds['segment_count'],44)
        self.assertEqual(ds['cycle_count'],23)
        groups=ds['comparable_cycle_groups']
        self.assertGreaterEqual(len(groups),6)
        self.assertEqual(ds['recommended_cycles'],[17,18])
        for group in groups:
            self.assertGreaterEqual(len(group['cycles']),2)
            self.assertLessEqual(group['duration_max_s']/group['duration_min_s'],1.30)

    @unittest.skipUnless(os.getenv('METROHM_SELF_DISCHARGE_SAMPLE'),'Set METROHM_SELF_DISCHARGE_SAMPLE')
    def test_ocp_recording_intervals_stay_separate(self):
        doc=read_nox(os.getenv('METROHM_SELF_DISCHARGE_SAMPLE'))
        ocp=next(d for d in doc['datasets'] if d['kind']=='OCP')
        self.assertEqual(ocp['point_count'],72000)
        self.assertEqual(ocp['cycle_count'],6)
        self.assertEqual(ocp['comparable_cycle_groups'],[])


if __name__=='__main__':
    unittest.main()
