import math
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from nrbf_lite import all_streams, Reader, NrbfError
import io
from nox_reader import read_nox, export_csv


class ReaderTests(unittest.TestCase):
    def test_nested_primitive_arrays(self):
        header=b'\x00'+struct.pack('<iiii',1,-1,1,0)
        # A one-element BinaryArray of PrimitiveArray<Int32> contains an
        # ArraySinglePrimitive record, not an inline Int32 scalar.
        outer=b'\x07'+struct.pack('<iBi',1,0,1)+struct.pack('<iBB',1,7,8)
        inner=b'\x0f'+struct.pack('<iiBii',2,2,8,42,-7)
        self.assertEqual(Reader(io.BytesIO(header+outer+inner+b'\x0b')).parse(),[[42,-7]])

    def test_null_run_cannot_overflow_array(self):
        header=b'\x00'+struct.pack('<iiii',1,-1,1,0)
        array=b'\x10'+struct.pack('<ii',1,1)
        with self.assertRaisesRegex(NrbfError,'exceeds'):
            Reader(io.BytesIO(header+array+b'\x0d\x02\x0b')).parse()

    def test_null_runs_must_be_positive(self):
        for record in [b'\x0d\x00',b'\x0e'+struct.pack('<i',-1)]:
            with self.subTest(record=record),self.assertRaisesRegex(NrbfError,'positive'):
                Reader(io.BytesIO(record)).record()

    def test_non_header_record_is_a_decoder_error(self):
        for record in [b'\x0a',b'\x08\x08'+struct.pack('<i',42)]:
            with self.subTest(record=record),self.assertRaisesRegex(NrbfError,'Not an NRBF'):
                Reader(io.BytesIO(record)).parse()

    def test_missing_root_object_is_rejected(self):
        with self.assertRaisesRegex(NrbfError,'Missing root'):
            Reader(io.BytesIO(b'\x00'+struct.pack('<iiii',1,-1,1,0)+b'\x0b')).parse()

    def test_minimal_nrbf(self):
        # Header(root=1, header=-1, version=1.0), string(id=1, "abc"), message end.
        payload=(b'\x00'+struct.pack('<iiii',1,-1,1,0)
                 +b'\x06'+struct.pack('<i',1)+b'\x03abc'+b'\x0b')
        with tempfile.TemporaryDirectory() as d:
            file=Path(d)/'test.bin'
            file.write_bytes(payload)
            parsed=all_streams(file)
            self.assertEqual(parsed[0][0],'abc')

    @unittest.skipUnless(os.environ.get('METROHM_SAMPLE'),
                         'Set METROHM_SAMPLE=/path/to/A110.001.nox to test the uploaded file')
    def test_uploaded_measurement(self):
        doc=read_nox(os.environ['METROHM_SAMPLE'])
        d=doc['datasets']
        self.assertEqual([(x['kind'],x['point_count']) for x in d],
                         [('CV',202),('CV',202),('EIS',40)])
        for ds in d:
            self.assertTrue(all(len(row)==len(ds['columns']) for row in ds['values']))
        # Check the frequency point's stored Nyquist and Bode curves are consistent.
        for f,zreal,zminusimag,mod,minusphase in d[-1]['values']:
            self.assertTrue(math.isclose(mod,math.hypot(zreal,zminusimag),rel_tol=1e-10))
            self.assertTrue(math.isclose(minusphase,math.degrees(math.atan2(zminusimag,zreal)),rel_tol=1e-9))
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'data.csv'
            export_csv(d[0],out)
            self.assertEqual(len(out.read_text(encoding='utf-8-sig').splitlines()),203)


if __name__=='__main__':unittest.main()
