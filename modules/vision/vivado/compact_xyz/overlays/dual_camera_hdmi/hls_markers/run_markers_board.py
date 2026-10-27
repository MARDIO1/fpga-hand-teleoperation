"""PS driver: DDR -> DMA -> HLS markers -> DMA -> candidate table.
No software color classification or connected-component calculation.
"""
import argparse
import json
import mmap
import os
from pathlib import Path
import time
import math
import numpy as np
from pynq import MMIO
from marker_transport import publish_points, publish_snapshot, snapshot_due, stage_eye

WIDTH, HEIGHT = 640, 720
BASE = 0x1e000000
INPUT = 0x400000
OUTPUT = 0x500000
RX_BYTES = 2048 * 40
COLORS = ('red', 'yellow', 'green', 'blue')

def validate_summary(summary,region_count):
    header=int(summary[0]);errors=header>>16
    if (header&65535)!=1 or int(summary[9])!=region_count or errors&~6 or (errors and region_count):
        raise RuntimeError('invalid summary/errors: '+str(summary.tolist()))
    return errors

class MarkerHardware:
    def __init__(self, thresholds):
        self.cfg = thresholds
        self.fd = os.open('/dev/mem', os.O_RDWR | os.O_SYNC)
        self.mem = mmap.mmap(self.fd, 0x1000000, flags=mmap.MAP_SHARED,
                            prot=mmap.PROT_READ | mmap.PROT_WRITE, offset=BASE)
        self.dma = MMIO(0x40400000, 0x1000)
        self.ip = MMIO(0x43c20000, 0x1000)
        self.dma.write(0, 4)
        self.wait(lambda: not self.dma.read(0) & 4, 'DMA reset')
        self.dma.write(0, 1)
        self.dma.write(0x30, 1)
        self.ip.write(0x20, WIDTH)
        self.ip.write(0x28, HEIGHT)
        self.ip.write(0x30, thresholds['min_area'])
        self.ip.write(0x38, thresholds['max_area'])
        self.scratch = np.empty((HEIGHT,WIDTH),dtype='<u2')

    @staticmethod
    def wait(condition, name):
        deadline = time.monotonic() + 3
        while not condition():
            if time.monotonic() > deadline:
                raise RuntimeError(name + ' timed out')
            time.sleep(0.0001)

    def eye(self, pixels, eye, sequence, timestamp):
        if pixels.shape != (HEIGHT, WIDTH) or pixels.dtype != np.dtype('<u2'):
            raise ValueError('expected 640x720 RGB565')
        started = time.monotonic()
        stage_started=time.monotonic()
        payload_bytes=stage_eye(pixels,self.scratch,self.mem,INPUT)
        input_stage_ms=(time.monotonic()-stage_started)*1000
        for i, color in enumerate(COLORS):
            t = self.cfg[eye][color]
            self.ip.write(0x10+i*4, t['h_min'] | t['h_max']<<8 | t['s_min']<<16 | t['v_min']<<24)
        self.ip.write(0x40, sequence)
        self.ip.write(0x48, timestamp & 0xffffffff)
        self.ip.write(0x4c, timestamp >> 32)
        self.dma.write(4, 0x7000)
        self.dma.write(0x34, 0x7000)
        self.dma.write(0x48, BASE+OUTPUT)
        self.dma.write(0x58, RX_BYTES)
        hardware_start = time.monotonic()
        self.ip.write(0, 1)
        self.dma.write(0x18, BASE+INPUT)
        self.dma.write(0x28, payload_bytes)
        def complete():
            tx, rx = self.dma.read(4), self.dma.read(0x34)
            if (tx | rx) & 0x770:
                raise RuntimeError('DMA error tx=%08x rx=%08x' % (tx, rx))
            return bool(tx & rx & 0x1000)
        self.wait(complete, 'marker transfer')
        self.wait(lambda: bool(self.ip.read(0) & 4), 'HLS idle')
        hardware_ms = (time.monotonic()-hardware_start)*1000
        received = self.dma.read(0x58)
        if not 40 <= received <= RX_BYTES or received % 40:
            raise RuntimeError('invalid result length %d' % received)
        words = np.frombuffer(self.mem[OUTPUT:OUTPUT+received], dtype='<u4').reshape(-1,10)
        summary = words[-1]
        errors=validate_summary(summary,len(words)-1)
        if int(summary[6])!=sequence or (int(summary[7])|int(summary[8])<<32)!=timestamp:
            raise RuntimeError('summary frame/timestamp mismatch')
        points = []
        for row in words[:-1]:
            w = [int(x) for x in row]
            color = (w[0]>>8)&255
            if w[0]&255 or w[0]>>16 or not 1 <= color <= 4 or w[6] != sequence or (w[7]|w[8]<<32) != timestamp or not w[1]:
                raise RuntimeError('invalid region packet')
            xmin,ymin = w[4]&65535,w[4]>>16
            xmax,ymax = w[5]&65535,w[5]>>16
            points.append(dict(color=COLORS[color-1],u=w[2]/w[1],v=w[3]/w[1],
                area_px=w[1],sum_x=w[2],sum_y=w[3],bbox=[xmin,ymin,xmax-xmin+1,ymax-ymin+1]))
        points.sort(key=lambda p:(COLORS.index(p['color']),p['u'],p['v']))
        counts = {}
        for p in points:
            counts[p['color']] = counts.get(p['color'],0)+1
            p['label'] = p['color']+str(counts[p['color']])
        return points, dict(input_stage_ms=input_stage_ms,hardware_dma_ms=hardware_ms,total_eye_ms=(time.monotonic()-started)*1000,
            errors=errors,total_runs=int(summary[1]),max_row_runs=int(summary[2]),allocated_labels=int(summary[3]),bytes=received)

    def close(self):
        self.mem.close()
        os.close(self.fd)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--thresholds',default=str(Path(__file__).with_name('glove_color_thresholds.json')))
    parser.add_argument('--input',help='optional raw stereo RGB565 golden fixture')
    parser.add_argument('--output',default='/dev/shm/marker_results')
    parser.add_argument('--frames',type=int,default=1)
    parser.add_argument('--fps',type=float,default=30,help='processing rate ceiling, not guaranteed throughput')
    parser.add_argument('--snapshot-fps',type=float,default=0,help='optional image preview rate; 0: point tables only')
    parser.add_argument('--snapshot-format',choices=('bin','npz'),default='bin')
    parser.add_argument('--hdmi',action='store_true')
    parser.add_argument('--calibrated',action='store_true',help='use geometry HLS IP for experimental XYZ')
    parser.add_argument('--results-page',action='store_true',help='start HDMI on results page; S2 still toggles')
    args = parser.parse_args()
    if (args.frames < 0 or not math.isfinite(args.fps) or args.fps <= 0
            or not math.isfinite(args.snapshot_fps) or args.snapshot_fps < 0): parser.error('invalid frames/fps')
    output = Path(args.output);output.mkdir(parents=True,exist_ok=True)
    hardware = MarkerHardware(json.loads(Path(args.thresholds).read_text()))
    fixture=Path(args.input).read_bytes() if args.input else None
    if fixture is not None and len(fixture)!=1280*720*2:
        hardware.close();raise ValueError('invalid stereo frame length')
    display=matcher=None
    if args.hdmi or args.calibrated:
        from marker_display_control import DisplayController,SparseMatcher
        if args.calibrated:
            from calibrated_hardware import CalibratedHardwareMatcher
            matcher=CalibratedHardwareMatcher()
        else:matcher=SparseMatcher()
        if args.hdmi:display=DisplayController(args.results_page)
    try:
        index=0
        rate_start=time.monotonic();rate_frames=0
        camera=MMIO(0x41200000,0x1000)
        source_start=camera.read(8);capture_fps=recognition_fps=0.0
        last_snapshot=None;previous_cycle=None;cycle_samples=[]
        while args.frames==0 or index<args.frames:
            started=time.monotonic()
            timestamp=int(started*1000000)
            raw=fixture if fixture is not None else hardware.mem[:1280*720*2]
            if len(raw)!=1280*720*2: raise ValueError('invalid stereo frame length')
            frame=np.frombuffer(raw,dtype='<u2').reshape(720,1280)
            read_ms=(time.monotonic()-started)*1000
            candidates={};timings={}
            for eye,pixels in [('L',frame[:,640:]),('R',frame[:,:640])]:
                candidates[eye],timings[eye]=hardware.eye(pixels,eye,index,timestamp)
            result=dict(processing='PL HLS RGB565 HSV RLE-CCL; PS centroid',snapshot_sequence=index,
                board_read_start_us=timestamp,exposure_timestamp=None,source_frame_id=None,
                frame_consistency='unverified DDR snapshot',candidates=candidates,timings=timings,
                total_pair_ms=(time.monotonic()-started)*1000)
            result['capture_read_ms']=read_ms
            result['previous_complete_cycle']=previous_cycle
            result['publication_policy']=dict(snapshot_fps=args.snapshot_fps,snapshot_format=args.snapshot_format,
                                               points_every_cycle=True)
            rate_frames+=1
            rate_now=time.monotonic();rate_elapsed=rate_now-rate_start
            if rate_elapsed>=1.0:
                source_now=camera.read(8)
                capture_fps=((source_now-source_start)&0xffffffff)/rate_elapsed
                recognition_fps=rate_frames/rate_elapsed
                rate_start=rate_now;source_start=source_now;rate_frames=0
            result['capture_fps']=capture_fps;result['recognition_fps']=recognition_fps
            if matcher:
                post_started=time.monotonic()
                result['frame_errors']=timings['L'].get('errors',0)|timings['R'].get('errors',0)
                if result['frame_errors']:
                    selected,matches=dict(L=[],R=[]),[]
                else:
                    selected,matches=matcher.process(candidates)
                result['stereo_matching_ms']=(time.monotonic()-post_started)*1000
                result['selected']=selected;result['matches']=matches
                result['matching_reference']='marker_stereo.py exact C++ port'
                result['geometry_spec']=matcher.geometry
                result['metric_valid']=False
                result['metric_coordinates_available']=args.calibrated
                result['absolute_accuracy_certified']=False
                if args.calibrated:result['calibration']=matcher.calibration
                result['hdmi_page']=('results' if display.page else 'raw') if display else 'disabled'
                result['xyz_status']='experimental_calibrated_left_optical_mm' if args.calibrated else 'uncalibrated_raw_images'
                result['display_ids']='frame_local'
                result['total_pair_ms']=(time.monotonic()-started)*1000
                if display:
                    display_args=(selected,matches,index,timestamp,result['total_pair_ms'],result['frame_errors'],capture_fps,recognition_fps)
                    # The current results overlay uses the original eight-field publisher.
                    if args.calibrated:display.update(*(display_args+(True,)))
                    else:display.update(*display_args)
            result['processing_ms']=(time.monotonic()-started)*1000
            publish_started=time.monotonic()
            snapshot_ms=0.0
            if snapshot_due(publish_started,last_snapshot,args.snapshot_fps):
                publish_snapshot(output,frame,result,args.snapshot_format)
                snapshot_ms=(time.monotonic()-publish_started)*1000
                last_snapshot=time.monotonic()
            points_started=time.monotonic()
            publish_points(output,result)
            points_ms=(time.monotonic()-points_started)*1000
            active_ms=(time.monotonic()-started)*1000
            print('frame=%d L=%d R=%d processing_ms=%.2f full_active_ms=%.2f snapshot_ms=%.2f' %
                  (index,len(candidates['L']),len(candidates['R']),result['processing_ms'],active_ms,snapshot_ms),flush=True)
            index+=1
            time.sleep(max(0,1/args.fps-(time.monotonic()-started)))
            previous_cycle=dict(snapshot_sequence=index-1,processing_ms=result['processing_ms'],
                                snapshot_publish_ms=snapshot_ms,points_publish_ms=points_ms,
                                full_active_ms=active_ms,cycle_ms=(time.monotonic()-started)*1000)
            cycle_samples.append(previous_cycle)
            if len(cycle_samples)>=30 or (args.frames and index==args.frames):
                means={key:float(np.mean([v[key] for v in cycle_samples])) for key in previous_cycle if key!='snapshot_sequence'}
                report=dict(frames=len(cycle_samples),means_ms=means,
                            cycle_p95_ms=float(np.percentile([v['cycle_ms'] for v in cycle_samples],95)),
                            completed_hz=1000/means['cycle_ms'] if means['cycle_ms']>0 else None,capture_fps=capture_fps,
                            note='Complete cycle includes image/point publication and rate sleep; snapshot IDs are not exposure IDs.')
                temporary=output/'performance.json.tmp'
                temporary.write_text(json.dumps(report,separators=(',',':')))
                os.replace(str(temporary),str(output/'performance.json'))
                cycle_samples=[]
    finally:
        if display:display.close()
        hardware.close()
if __name__=='__main__': main()
