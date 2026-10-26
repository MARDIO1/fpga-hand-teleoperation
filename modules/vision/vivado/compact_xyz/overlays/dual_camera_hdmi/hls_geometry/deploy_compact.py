"""Upload the markers overlay bundle; quiesce video before loading it."""
from pathlib import Path
import shlex
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'scripts'))
from board_ssh import HOST,USER,PASSWORD,paramiko
HERE=Path(__file__).resolve().parent.parent/'hls_markers'
ROOT=HERE.parents[2]
REMOTE='/home/xilinx/overlays/pl_stereo_hdmi/compact_xyz_20261026'

def main():
    gate=HERE.parent/'output/compact_xyz/resource_gate.txt'
    values=gate.read_text().split();usage=dict(zip(values[::2],map(float,values[1::2])))
    capacities={'LUT':46200,'FF':92400,'DSP':160,'BRAM36':95}
    if set(usage)!=set(capacities) or any(usage[k]>.6*capacities[k] for k in capacities):
        raise SystemExit('Refusing deployment: resource gate is missing or exceeds 60 percent')
    files=[(HERE.parent/'output/compact_xyz'/('pl_stereo_compact_xyz'+ext),'pl_stereo_compact_xyz'+ext) for ext in ['.bit','.hwh']]
    files += [(HERE.parent/'glove_color_thresholds.json','glove_color_thresholds.json')]
    files += [(HERE/name,name) for name in ['run_markers_board.py','marker_transport.py','marker_display_control.py','marker_match.cpp','marker_match.hpp','test_marker_match.cpp','geometry_spec.json']]
    files += [(HERE.parent/'marker_stereo.py','marker_stereo.py')]
    files += [(HERE.parent/'hls_geometry'/name,name) for name in ['calibrated_hardware.py','calibration.json','geometry_registers.json','start_compact.py']]
    if not all(p.is_file() for p,_ in files):raise SystemExit('Build output missing')
    client=paramiko.SSHClient();client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST,username=USER,password=PASSWORD,timeout=15)
    def run(command,sudo=False):
        stdin,stdout,stderr=client.exec_command("sudo -S -p '' sh -c "+shlex.quote(command) if sudo else command,timeout=90)
        if sudo:stdin.write(PASSWORD+'\n');stdin.flush();stdin.channel.shutdown_write()
        out=stdout.read().decode();err=stderr.read().decode();code=stdout.channel.recv_exit_status()
        print(out,end='');print(err,end='',file=sys.stderr)
        if code:raise RuntimeError('remote command failed %d'%code)
    try:
        run('mkdir -p '+REMOTE)
        with client.open_sftp() as sftp:
            for source,name in files:sftp.put(str(source),REMOTE+'/'+name);print('uploaded',name)
        run('sha256sum '+REMOTE+'/*.bit '+REMOTE+'/*.hwh')
        run('cd '+REMOTE+' && g++ -std=c++11 -O2 marker_match.cpp test_marker_match.cpp -o test_marker_match && ./test_marker_match && g++ -std=c++11 -O2 -shared -fPIC marker_match.cpp -o libmarker_match.so')
        # Only stop the known camera/marker processes; no broad Python kill.
        run("pkill -TERM -f '^python3 -u run_markers_board.py( |$)' || true; pkill -TERM -f '^python3 -u run_ch19_display.py --live' || true",True)
        stop_script='''from pynq import MMIO
import time
dma=MMIO(0x40400000,4096)
dma.write(0,4)
deadline=time.monotonic()+3
while dma.read(0)&4:
    if time.monotonic()>deadline:raise RuntimeError('Marker DMA reset failed; refusing reload')
    time.sleep(.001)
v=MMIO(0x43000000,4096)
for control,status in [(0x30,0x34),(0,4)]:
    v.write(control,v.read(control)&~1)
    deadline=time.monotonic()+3
    while not v.read(status)&1:
        if time.monotonic()>deadline:raise RuntimeError('VDMA did not halt; refusing reload')
        time.sleep(.001)
    v.write(control,4)
    deadline=time.monotonic()+3
    while v.read(control)&4:
        if time.monotonic()>deadline:raise RuntimeError('VDMA reset failed; refusing reload')
        time.sleep(.001)
print('Old VDMA halted and reset')
'''
        run('python3 -c '+shlex.quote(stop_script),True)
        run('systemctl stop acz7015-hdmi.service',True)
        run('cd '+REMOTE+' && python3 -u start_compact.py',True)
    finally:client.close()
if __name__=='__main__':main()
