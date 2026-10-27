import contextlib
import importlib.util
import io
import json
import mmap
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np

from marker_transport import (decode_snapshot,publish_points,publish_snapshot,
                              snapshot_due,stage_eye,FRAME_BYTES,HEADER)


class TransportTests(unittest.TestCase):
    def setUp(self):
        root=Path(__file__).resolve().parents[3]/'output/test_tmp'
        root.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=root)
        self.folder=Path(self.tmp.name)
        self.assertEqual(self.folder.resolve().parent,root.resolve())

    def tearDown(self):
        self.tmp.cleanup()

    def test_exact_strided_eye_staging_in_real_mmap(self):
        frame=np.random.default_rng(7).integers(0,65536,(720,1280),dtype=np.uint16)
        scratch=np.empty((720,640),dtype='<u2')
        with (self.folder/'memory.bin').open('w+b') as stream:
            stream.truncate(FRAME_BYTES)
            with mmap.mmap(stream.fileno(),FRAME_BYTES) as memory:
                for pixels in (frame[:,640:],frame[:,:640]):
                    size=stage_eye(pixels,scratch,memory,64)
                    self.assertEqual(size,921600)
                    self.assertEqual(memory[64:64+size],pixels.tobytes(order='C'))
                with self.assertRaises(ValueError):stage_eye(frame,scratch,memory,0)

    def test_both_snapshot_formats_preserve_same_frame_and_metadata(self):
        frame=np.arange(720*1280,dtype=np.uint16).reshape(720,1280)
        result=dict(snapshot_sequence=123,candidates=dict(L=[],R=[]),errors=0)
        for fmt in ('bin','npz'):
            publish_snapshot(self.folder,frame,result,fmt)
            decoded,metadata=decode_snapshot((self.folder/('latest.'+fmt)).read_bytes())
            np.testing.assert_array_equal(decoded,frame)
            self.assertEqual(metadata,result)
            self.assertFalse((self.folder/('latest.'+fmt+'.tmp')).exists())
        result['snapshot_sequence']=124
        publish_points(self.folder,result)
        self.assertEqual(json.loads((self.folder/'latest.json').read_text())['snapshot_sequence'],124)
        self.assertEqual(decode_snapshot((self.folder/'latest.bin').read_bytes())[1]['snapshot_sequence'],123)

    def test_disabled_and_limited_publication(self):
        self.assertFalse(snapshot_due(0,None,0))
        self.assertTrue(snapshot_due(0,None,1))
        self.assertFalse(snapshot_due(.9,0,1))
        self.assertTrue(snapshot_due(1,0,1))
        with self.assertRaises(ValueError):snapshot_due(0,None,float('nan'))

    def test_bad_packets_rejected(self):
        for packet in (b'MKR1',HEADER.pack(b'MKR1',1,0),b'garbage'):
            with self.assertRaises(ValueError):decode_snapshot(packet)
        with self.assertRaises(ValueError):
            publish_snapshot(self.folder,np.zeros((720,640),np.uint16),{})

    def test_driver_loop_point_only_and_preview_without_hardware(self):
        # Real loop/publication logic; only PL register/DMA access is replaced.
        path=Path(__file__).with_name('run_markers_board.py')
        fake_pynq=types.ModuleType('pynq')
        class Registers:
            def __init__(self,*args):pass
            def read(self,*args):return 0
        fake_pynq.MMIO=Registers
        with patch.dict(sys.modules,{'pynq':fake_pynq}):
            spec=importlib.util.spec_from_file_location('driver_under_test',path)
            driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
        class Hardware:
            def __init__(self,config):self.closed=False
            def eye(self,pixels,eye,index,timestamp):
                return [],dict(errors=0,hardware_dma_ms=9.5)
            def close(self):self.closed=True
        fake_display=types.ModuleType('marker_display_control')
        class Display:
            page=True
            calls=0
            def __init__(self,*args):pass
            def update(self,selected,matches,sequence,timestamp,pair_ms,errors,capture_fps,recognition_fps):
                Display.calls+=1
            def close(self):pass
        class Matcher:
            geometry={'max_aspect_ratio':2}
            def process(self,candidates):return candidates,[]
        fake_display.DisplayController=Display
        fake_display.SparseMatcher=Matcher
        raw=self.folder/'input.rgb565'
        np.zeros((720,1280),np.uint16).tofile(raw)
        cfg=self.folder/'thresholds.json';cfg.write_text('{}')
        for snapshot_rate in (0,1):
            output=self.folder/('run'+str(snapshot_rate))
            args=['driver','--input',str(raw),'--thresholds',str(cfg),'--output',str(output),
                  '--frames','3','--fps','100','--snapshot-fps',str(snapshot_rate),'--hdmi']
            with patch.object(driver,'MarkerHardware',Hardware),patch.object(sys,'argv',args),patch.dict(sys.modules,{'marker_display_control':fake_display}),contextlib.redirect_stdout(io.StringIO()):
                driver.main()
            result=json.loads((output/'latest.json').read_text())
            self.assertEqual(result['snapshot_sequence'],2)
            self.assertEqual(result['previous_complete_cycle']['snapshot_sequence'],1)
            self.assertFalse((output/'latest.npz').exists())
            self.assertEqual((output/'latest.bin').exists(),bool(snapshot_rate))
            perf=json.loads((output/'performance.json').read_text())
            self.assertEqual(perf['frames'],3)
            self.assertGreater(perf['completed_hz'],0)
            if snapshot_rate:
                _,snapshot=decode_snapshot((output/'latest.bin').read_bytes())
                self.assertEqual(snapshot['snapshot_sequence'],0)
        self.assertEqual(Display.calls,6)


if __name__=='__main__':unittest.main()
