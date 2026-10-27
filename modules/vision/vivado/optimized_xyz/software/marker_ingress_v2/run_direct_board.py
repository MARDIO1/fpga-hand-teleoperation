"""Direct-reader driver. For the V2 bitstream ONLY; never downloads an overlay.
Capture completion is gated on both EOF and VDMA IOC before granting a lease.
Any transfer error is fatal: stop the runner and reload after diagnosis; do not reuse stale points.
"""
import argparse,json,mmap,os,sys,time
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE.parent/'hls_markers'),str(HERE.parent/'hls_geometry')]
from run_markers_board import MarkerHardware,validate_summary,COLORS,BASE,OUTPUT,RX_BYTES,WIDTH,HEIGHT
from marker_transport import snapshot_due
from process_publisher import ProcessPublisher
SLOTS=(0x1e000000,0x1e200000,0x1e600000)

class DirectMarkerHardware(MarkerHardware):
    def __init__(self,thresholds):
        from pynq import MMIO
        self.control=MMIO(0x43c60000,0x1000)
        if self.control.read(0)!=0x4d495632 or self.control.read(4)!=0x20b:
            raise RuntimeError('V2 hardware ID/capability mismatch; use matching bit/hwh')
        if self.control.read(12)&0xf01:
            raise RuntimeError('V2 already active; stop its owner first')
        self.cfg=thresholds
        self.fd=os.open('/dev/mem',os.O_RDWR|os.O_SYNC)
        self.mem=mmap.mmap(self.fd,0x1000000,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ|mmap.PROT_WRITE,offset=BASE)
        self.dma=MMIO(0x40400000,0x1000);self.ip=MMIO(0x43c20000,0x1000)
        self.capture=MMIO(0x43000000,0x1000)
        self.camera=MMIO(0x41200000,0x1000)
        self.control.write(0x38,0);self.control.write(0x38,1)
        # V2 DMA has S2MM only. Never access absent MM2S registers.
        self.dma.write(0x30,4);self.wait(lambda:not self.dma.read(0x30)&4,'result DMA reset')
        self.dma.write(0x30,1)
        for reg,value in [(0x20,WIDTH),(0x28,HEIGHT),(0x30,thresholds['min_area']),(0x38,thresholds['max_area'])]:self.ip.write(reg,value)
        self.pending=None;self.token=None

    @staticmethod
    def wait(condition,name,timeout=3):
        deadline=time.monotonic()+timeout
        while not condition():
            if time.monotonic()>deadline:raise RuntimeError(name+' timed out; preserve lease and reload safely')
            time.sleep(0.0001)

    def check(self):
        status=self.control.read(12)
        if status&0x1004:raise RuntimeError('V2 controller error status=%08x detail=%08x'%(status,self.control.read(0x2c)))
        return status

    def start_capture(self,base):
        if base not in SLOTS or self.pending is not None or (self.token and base==self.token['base']):
            raise ValueError('capture slot still owned or outside reserved whitelist')
        if self.check()&0x700:raise RuntimeError('previous capture not consumed')
        # Gate is closed. Reset VDMA before updating its single frame-store address.
        self.capture.write(0x30,4);self.wait(lambda:not self.capture.read(0x30)&4,'capture reset')
        self.capture.write(0x34,0x7770)
        self.capture.write(0xac,base);self.capture.write(0xa4,2560);self.capture.write(0xa8,2560)
        self.capture.write(0x30,0x1003);self.capture.write(0xa0,720)
        self.control.write(0x10,base);self.control.write(0x34,1);self.check()
        self.pending=base

    def acquire_pair(self):
        if self.token is not None or self.pending is None:raise RuntimeError('invalid lease transition')
        def complete():
            status=self.check();vdma=self.capture.read(0x34)
            if vdma&0x0ff0:raise RuntimeError('capture VDMA error %08x'%vdma)
            return bool(status&0x400)
        self.wait(complete,'complete video frame',25)
        # Gate has sent every pixel and is closed. Stop only after EOF, then
        # wait for VDMA to complete outstanding operations before granting lease.
        self.capture.write(0x30,self.capture.read(0x30)&~1)
        self.wait(lambda:bool(self.capture.read(0x34)&1),'capture writes halted')
        if self.capture.read(0x34)&0x8ff0:raise RuntimeError('capture error after halt')
        self.control.write(8,16);self.check()
        token=dict(base=self.control.read(0x28),frame_id=self.control.read(0x1c),
                   timestamp_us=self.control.read(0x20)|(self.control.read(0x24)<<32))
        if token['base']!=self.pending or not self.control.read(12)&0x800:raise RuntimeError('lease mismatch')
        self.pending=None;self.token=token
        return token

    def release_pair(self):
        if self.token is None or self.control.read(12)&1:raise RuntimeError('cannot release active reader')
        self.control.write(8,8);self.check();self.token=None

    def snapshot(self,token):
        if token!=self.token:raise RuntimeError('snapshot requires active lease')
        start=token['base']-BASE
        return np.frombuffer(self.mem[start:start+1280*720*2],dtype='<u2').reshape(720,1280)

    def eye(self,token,eye):
        if token!=self.token or eye not in ('L','R'):raise ValueError('invalid eye/lease')
        started=time.monotonic();sequence=token['frame_id'];timestamp=token['timestamp_us']
        for i,color in enumerate(COLORS):
            t=self.cfg[eye][color]
            self.ip.write(0x10+i*4,t['h_min']|t['h_max']<<8|t['s_min']<<16|t['v_min']<<24)
        self.ip.write(0x40,sequence);self.ip.write(0x48,timestamp&0xffffffff);self.ip.write(0x4c,timestamp>>32)
        self.dma.write(0x34,0x7000);self.dma.write(0x48,BASE+OUTPUT);self.dma.write(0x58,RX_BYTES)
        self.control.write(0x18,int(eye=='L'))
        hardware_start=time.monotonic();self.ip.write(0,1);self.control.write(8,1)
        def complete():
            status=self.check();rx=self.dma.read(0x34)
            if rx&0x770:raise RuntimeError('result DMA error %08x'%rx)
            return bool(status&2 and not status&1 and rx&0x1000)
        self.wait(complete,'direct marker transfer')
        self.wait(lambda:bool(self.ip.read(0)&4),'HLS idle')
        if self.control.read(0x30)!=WIDTH*HEIGHT:raise RuntimeError('reader pixel count mismatch')
        hardware_ms=(time.monotonic()-hardware_start)*1000
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
        return points, dict(input_stage_ms=0.0,hardware_dma_ms=hardware_ms,total_eye_ms=(time.monotonic()-started)*1000,
            errors=errors,total_runs=int(summary[1]),max_row_runs=int(summary[2]),allocated_labels=int(summary[3]),bytes=received)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--frames',type=int,default=1);p.add_argument('--fps',type=float,default=30,help='software ceiling; 0 disables limiting')
    p.add_argument('--snapshot-fps',type=float,default=0)
    p.add_argument('--thresholds',default=str(HERE.parent/'glove_color_thresholds.json'))
    p.add_argument('--output',default='/dev/shm/marker_results_v2')
    a=p.parse_args()
    if a.frames<0 or not np.isfinite(a.fps) or a.fps<0 or not np.isfinite(a.snapshot_fps) or a.snapshot_fps<0:p.error('invalid rate/frame count; fps=0 disables software limiting')
    from calibrated_hardware import CalibratedHardwareMatcher
    matcher=CalibratedHardwareMatcher();hardware=DirectMarkerHardware(json.loads(Path(a.thresholds).read_text()))
    output=Path(a.output);output.mkdir(parents=True,exist_ok=True)
    publisher=ProcessPublisher(output)
    last_snapshot=None;index=0;cycles=[]
    rate_time=time.monotonic();source_count=hardware.camera.read(8);capture_fps=0.0
    try:
        hardware.start_capture(SLOTS[0])
        previous_completed=time.monotonic()
        while a.frames==0 or index<a.frames:
            started=time.monotonic()
            held_slots=publisher.held_slots
            next_base=next(base for base in SLOTS if base!=hardware.pending and base not in held_slots)
            acquire_started=time.monotonic();token=hardware.acquire_pair()
            capture_wait_ms=(time.monotonic()-acquire_started)*1000
            # Capture the other slot once while both eyes use the leased immutable slot.
            more=a.frames==0 or index+1<a.frames
            if more:hardware.start_capture(next_base)
            candidates={};timings={}
            for eye in ('L','R'):candidates[eye],timings[eye]=hardware.eye(token,eye)
            errors=timings['L']['errors']|timings['R']['errors']
            selected,matches=({'L':[],'R':[]},[]) if errors else matcher.process(candidates)
            now=time.monotonic()
            if now-rate_time>=1:
                source_now=hardware.camera.read(8);capture_fps=((source_now-source_count)&0xffffffff)/(now-rate_time)
                rate_time=now;source_count=source_now
            result=dict(capture_fps=capture_fps,recognition_fps=(1000/float(np.mean(cycles)) if cycles else 0.0),processing='PL direct DDR RGB565 RLE-CCL and geometry; PS C++ matching',
                snapshot_sequence=index,source_frame_id=token['frame_id'],capture_boundary_timestamp_us=token['timestamp_us'],
                exposure_timestamp=None,frame_consistency='leased frame; complete EOF plus VDMA halted',frame_token=token,
                candidates=candidates,timings=timings,selected=selected,matches=matches,frame_errors=errors,
                metric_coordinates_available=True,absolute_accuracy_certified=False,metric_valid=False,
                calibration=matcher.calibration,xyz_status='experimental_calibrated_left_optical_mm',display_ids='frame_local',
                capture_wait_ms=capture_wait_ms,total_pair_ms=(time.monotonic()-started)*1000,hdmi_page='disabled')
            preview_token=None
            if snapshot_due(time.monotonic(),last_snapshot,a.snapshot_fps):
                preview_token=token
            # Reserve preview ownership before releasing the hardware lease.
            if publisher.submit(result,token=preview_token):last_snapshot=time.monotonic()
            hardware.release_pair()
            index+=1
            if a.fps:time.sleep(max(0,1/a.fps-(time.monotonic()-started)))
            completed=time.monotonic();cycles.append((completed-previous_completed)*1000);previous_completed=completed
            if len(cycles)>30:cycles.pop(0)
            report=dict(frames=len(cycles),cycle_mean_ms=float(np.mean(cycles)),cycle_p95_ms=float(np.percentile(cycles,95)),completed_hz=1000/float(np.mean(cycles)),
                points_published=publisher.points_written,points_dropped=publisher.points_dropped,
                previews_published=publisher.previews_written,previews_dropped=publisher.previews_dropped)
            temp=output/'performance.json.tmp';temp.write_text(json.dumps(report));os.replace(str(temp),str(output/'performance.json'))
            print('frame=%d source=%d pairs=%d cycle_ms=%.2f'%(index,token['frame_id'],len(matches),cycles[-1]),flush=True)
    finally:
        # An error may leave AXI transactions in flight. Do not release/reuse that slot.
        hardware.close()
        publisher.close()

if __name__=='__main__':main()
